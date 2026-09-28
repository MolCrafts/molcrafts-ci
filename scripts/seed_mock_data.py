"""Seed Git-friendly mock index data using ``import molci as mci``.

Writes tracked snapshots under ``.mock-data/`` (gitignored) and refreshes
``site/mock/fixtures.ts`` consumed by ``rspack-plugin-mock`` during
``npm run dev``.

Safe to re-run: clears the scratch root first.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import molci as mci

ROOT = Path(__file__).resolve().parents[1]
# Deliberately NOT the tracked `data/`. These snapshots carry invented commit
# SHAs and workflow ids; when they lived under `data/` they were committed and
# published as if they were real history. The dev server reads fixtures.ts, not
# this tree, so a scratch root serves the same purpose and cannot be committed.
DATA = ROOT / ".mock-data"
FIXTURES_TS = ROOT / "site" / "mock" / "fixtures.ts"

# Enough points to fill HISTORY_DEPTH (12) sparklines with room to spare.
GENERATIONS = 12
# Day 0 of the mock timeline — newest generation lands "today".
ANCHOR = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _clear_mock_trees() -> None:
    """The scratch root is rebuilt from scratch; ingest refuses to overwrite."""
    if DATA.exists():
        shutil.rmtree(DATA)


def _commit(seed: str, generation: int) -> str:
    """32 hex chars; first 12 unique per (seed, generation) so snapshot ids differ."""
    base = f"{seed}{generation:04d}".encode()
    # Expand deterministically without importing hashlib just for display length.
    hexed = "".join(f"{(b + generation * 17) % 256:02x}" for b in (base * 4)[:16])
    return hexed


def _stamp(generation: int, hour: int = 9) -> str:
    """Older generations further in the past; generation 1 is oldest."""
    days_ago = GENERATIONS - generation
    when = ANCHOR - timedelta(days=days_ago, hours=max(0, 12 - hour))
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _entry(
    *,
    record: str,
    project_repo: str,
    commit: str,
    profile: str,
    producer: str,
    timestamp: str,
    workflow_run: int,
    generation: int,
    payload: dict,
) -> mci.Snapshot:
    return mci.Snapshot(
        manifest=mci.Manifest(
            record=record,
            source=mci.Source(
                repository=project_repo,
                commit=commit,
                ref="refs/heads/main",
                workflow_run=workflow_run,
                timestamp=timestamp,
            ),
            producer=producer,
            profile=profile,
            tracking=mci.Tracking(enabled=True, generation=generation),
        ),
        payload=payload,
    )


def _series(
    project: str,
    repo: str,
    record: str,
    *,
    profile: str,
    producer: str,
    workflow_base: int,
    hour: int,
    payload_at,
    generations: int = GENERATIONS,
) -> list[tuple[str, mci.Snapshot]]:
    out: list[tuple[str, mci.Snapshot]] = []
    for gen in range(1, generations + 1):
        out.append(
            (
                project,
                _entry(
                    record=record,
                    project_repo=repo,
                    commit=_commit(f"{project}-{record}-{profile}", gen),
                    profile=profile,
                    producer=producer,
                    timestamp=_stamp(gen, hour=hour),
                    workflow_run=workflow_base + gen,
                    generation=gen,
                    payload=payload_at(gen),
                ),
            )
        )
    return out


def _tests_payload(gen: int, *, base: int, fail_at: set[int] | None = None) -> dict:
    failed = 2 + (gen % 3) if fail_at and gen in fail_at else 0
    passed = base + gen * 3 - failed
    return {"passed": passed, "failed": failed, "skipped": gen % 4}


def _coverage_payload(gen: int, *, start: float, step: float, files: list[dict]) -> dict:
    lines = round(min(99.5, start + step * (gen - 1)), 1)
    return {
        "totals": {
            "lines": lines,
            "branches": round(lines - 12.5, 1),
            "functions": round(min(99.9, lines + 4.0), 1),
            "statements": round(lines - 0.8, 1),
        },
        "files": files,
    }


def _bench_payload(gen: int, *, start_ns: float, improve: float) -> dict:
    # Lower is better — improve gently, with a small regression mid-series.
    mean = start_ns - improve * (gen - 1)
    if gen == 7:
        mean += improve * 3
    return {"metrics": {"mean_ns": round(mean, 3)}}


def _regression_payload(gen: int) -> dict:
    err = 5.0e-7 / gen
    if gen == 5:
        err = 2.4e-6
    return {"max_abs_error": err}


def _build_seeds() -> list[tuple[str, mci.Snapshot]]:
    seeds: list[tuple[str, mci.Snapshot]] = []

    # molpy — richest: tests/coverage/benchmark/regression, one failed run.
    seeds += _series(
        "molpy",
        "MolCrafts/molpy",
        "tests",
        profile="linux-x86_64",
        producer="pytest",
        workflow_base=1200,
        hour=8,
        payload_at=lambda g: _tests_payload(g, base=400, fail_at={4, 9}),
    )
    seeds += _series(
        "molpy",
        "MolCrafts/molpy",
        "coverage",
        profile="linux-x86_64",
        producer="coverage.py",
        workflow_base=1200,
        hour=8,
        payload_at=lambda g: _coverage_payload(
            g,
            start=74.0,
            step=0.9,
            files=[
                {"path": "molpy/core/frame.py", "lines": 90.1, "uncovered": [55, 56]},
                {"path": "molpy/io/xyz.py", "lines": 74.0, "uncovered": [12, 13, 40]},
                {"path": "molpy/ff/amber.py", "lines": 61.2, "uncovered": [8, 9, 10, 88]},
            ],
        ),
    )
    seeds += _series(
        "molpy",
        "MolCrafts/molpy",
        "benchmark",
        profile="linux-x86_64",
        producer="pytest-benchmark",
        workflow_base=1200,
        hour=9,
        payload_at=lambda g: _bench_payload(g, start_ns=18.4, improve=0.45),
    )
    seeds += _series(
        "molpy",
        "MolCrafts/molpy",
        "regression",
        profile="linux-x86_64",
        producer="molpy-numerical",
        workflow_base=1200,
        hour=9,
        payload_at=_regression_payload,
        generations=10,
    )

    # molrs — dual-profile benchmarks.
    seeds += _series(
        "molrs",
        "MolCrafts/molrs",
        "tests",
        profile="linux-x86_64",
        producer="cargo-test",
        workflow_base=440,
        hour=10,
        payload_at=lambda g: _tests_payload(g, base=1580, fail_at={6}),
    )
    seeds += _series(
        "molrs",
        "MolCrafts/molrs",
        "coverage",
        profile="linux-x86_64",
        producer="llvm-cov",
        workflow_base=440,
        hour=10,
        payload_at=lambda g: _coverage_payload(
            g,
            start=81.0,
            step=0.6,
            files=[
                {
                    "path": "molrs/src/spatial/neighbors.rs",
                    "lines": 94.2,
                    "uncovered": [412, 418],
                },
                {
                    "path": "molrs/src/md/lj.rs",
                    "lines": 81.0,
                    "uncovered": [88, 91, 120],
                },
            ],
        ),
    )
    seeds += _series(
        "molrs",
        "MolCrafts/molrs",
        "benchmark",
        profile="linux-x86_64",
        producer="criterion",
        workflow_base=440,
        hour=11,
        payload_at=lambda g: {
            "suite": "neighbor_list",
            "metrics": {"mean_ns": round(42.0 - 0.8 * (g - 1), 2)},
        },
    )
    seeds += _series(
        "molrs",
        "MolCrafts/molrs",
        "benchmark",
        profile="macos-aarch64",
        producer="criterion",
        workflow_base=460,
        hour=11,
        payload_at=lambda g: {
            "suite": "neighbor_list",
            "metrics": {"mean_ns": round(38.5 - 0.7 * (g - 1), 2)},
        },
        generations=10,
    )

    # molcrafts-molrec
    seeds += _series(
        "molcrafts-molrec",
        "MolCrafts/molcrafts-molrec",
        "tests",
        profile="default",
        producer="pytest",
        workflow_base=90,
        hour=11,
        payload_at=lambda g: _tests_payload(g, base=70),
        generations=10,
    )
    seeds += _series(
        "molcrafts-molrec",
        "MolCrafts/molcrafts-molrec",
        "coverage",
        profile="default",
        producer="coverage.py",
        workflow_base=90,
        hour=11,
        payload_at=lambda g: _coverage_payload(
            g,
            start=86.0,
            step=0.5,
            files=[
                {"path": "src/molrec/schema.py", "lines": 97.0, "uncovered": [210]},
                {
                    "path": "src/molrec/bench.py",
                    "lines": 78.5,
                    "uncovered": [44, 45, 67, 68],
                },
            ],
        ),
        generations=10,
    )
    seeds += _series(
        "molcrafts-molrec",
        "MolCrafts/molcrafts-molrec",
        "molrec",
        profile="default",
        producer="molrec",
        workflow_base=90,
        hour=12,
        payload_at=lambda g: {
            "schema_version": "0.1.0",
            "cases": 40 + g * 2,
            "passed": 40 + g * 2 - (1 if g == 3 else 0),
        },
        generations=8,
    )

    # molcrafts-ci self-hosting
    seeds += _series(
        "molcrafts-ci",
        "MolCrafts/molcrafts-ci",
        "tests",
        profile="linux-x86_64",
        producer="pytest",
        workflow_base=10,
        hour=13,
        payload_at=lambda g: _tests_payload(g, base=30),
        generations=10,
    )
    seeds += _series(
        "molcrafts-ci",
        "MolCrafts/molcrafts-ci",
        "coverage",
        profile="linux-x86_64",
        producer="coverage.py",
        workflow_base=10,
        hour=13,
        payload_at=lambda g: _coverage_payload(
            g,
            start=88.0,
            step=0.4,
            files=[
                {
                    "path": "src/molcrafts_ci/persist.py",
                    "lines": 96.0,
                    "uncovered": [140],
                },
                {
                    "path": "src/molcrafts_ci/cli.py",
                    "lines": 82.0,
                    "uncovered": [12, 44, 45],
                },
            ],
        ),
        generations=10,
    )

    return seeds


def _published_from_entries(entries: dict[str, list[dict]]) -> dict[str, str]:
    published: dict[str, str] = {}
    for key, rows in entries.items():
        project = key.split("/", 1)[0]
        for row in rows:
            stamp = row.get("timestamp")
            if not isinstance(stamp, str):
                continue
            latest = published.get(project)
            if latest is None or stamp > latest:
                published[project] = stamp
    return published


def _export_fixtures() -> None:
    """Rebuild TypeScript fixtures from the JSONL index + snapshot files molci wrote."""
    index_root = DATA / "index"
    indexes: list[str] = []
    entries: dict[str, list[dict]] = {}
    if index_root.exists():
        for path in sorted(index_root.rglob("*.jsonl")):
            rel = path.relative_to(DATA).as_posix()
            indexes.append(f"data/{rel}")
            project = path.parent.name
            record = path.stem
            key = f"{project}/{record}"
            rows: list[dict] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
            entries[key] = rows

    # Prefer the listing molci wrote (includes published); fall back to deriving.
    listing_path = DATA / "index-listing.json"
    published: dict[str, str] = {}
    if listing_path.exists():
        listing = json.loads(listing_path.read_text(encoding="utf-8"))
        published = dict(listing.get("published") or {})
        if listing.get("indexes"):
            # Keep fixture paths prefixed the way the mock already serves them.
            indexes = [p if p.startswith("data/") else f"data/{p}" for p in listing["indexes"]]
    if not published:
        published = _published_from_entries(entries)

    snapshots: dict[str, dict] = {}
    snap_root = DATA / "snapshots"
    if snap_root.exists():
        for path in sorted(snap_root.rglob("*.json")):
            rel = path.relative_to(DATA).as_posix()
            snapshots[rel] = json.loads(path.read_text(encoding="utf-8"))

    payload = {
        "indexes": indexes,
        "published": published,
        "entries": entries,
        "snapshots": snapshots,
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    FIXTURES_TS.write_text(
        "/**\n"
        " * AUTO-GENERATED by ``scripts/seed_mock_data.py`` (molci ingest).\n"
        " * Do not edit by hand — re-run the seeder.\n"
        " */\n\n"
        "export type IndexEntry = {\n"
        "  snapshot_id: string;\n"
        "  path: string;\n"
        "  record: string;\n"
        "  generation: number;\n"
        "  profile: string;\n"
        "  repository: string;\n"
        "  commit: string;\n"
        "  ref: string;\n"
        "  workflow_run: number | null;\n"
        "  producer: string;\n"
        "  timestamp: string | null;\n"
        "  [key: string]: unknown;\n"
        "};\n\n"
        "export type MockFixtures = {\n"
        "  indexes: string[];\n"
        "  published: Record<string, string>;\n"
        "  entries: Record<string, IndexEntry[]>;\n"
        "  snapshots: Record<string, unknown>;\n"
        "};\n\n"
        f"export const fixtures: MockFixtures = {body} as const;\n",
        encoding="utf-8",
    )


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    _clear_mock_trees()

    seeds = _build_seeds()
    for project, snap in seeds:
        mci.ingest_snapshot(DATA, project, snap)

    _export_fixtures()
    print(f"seeded {len(seeds)} snapshots under {DATA}")
    print(f"wrote {FIXTURES_TS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
