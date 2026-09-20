#!/usr/bin/env python3
"""
Turn this repository's own test and coverage results into Snapshots.

molcrafts-ci is its own first producer. The run that tests this package also
publishes what it measured, through the same ``actions/submit`` every downstream
repository calls — so the publish path is exercised on every push to master
rather than only when someone else adopts it. If it breaks, it breaks here.

This is a producer, not infrastructure: it reads the tools' native output
(JUnit XML from pytest, JSON from coverage.py) and owns the payload shape.
``molcrafts_ci`` never interprets a payload.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import molci as mci


def profile() -> str:
    """Machine identity, so one project's history stays comparable within a runner."""
    machine = {"AMD64": "x86_64", "arm64": "aarch64"}.get(platform.machine(), platform.machine())
    return f"{platform.system().lower()}-{machine}"


def source(*, tracked: bool) -> mci.Source:
    run = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    commit = os.environ.get("GITHUB_SHA")
    if tracked and not commit:
        # A snapshot id derives from the commit. Publishing history under a
        # placeholder would collide with every other run that did the same.
        raise SystemExit("--track needs GITHUB_SHA; refusing to publish a placeholder commit")
    return mci.Source(
        repository=os.environ.get("GITHUB_REPOSITORY", "MolCrafts/molcrafts-ci"),
        # A local run has no SHA; a placeholder keeps the id stable and
        # obviously not a commit.
        commit=commit or "0" * 40,
        ref=os.environ.get("GITHUB_REF"),
        workflow_run=int(run) if run else None,
        run_attempt=int(attempt) if attempt else None,
        producer_version=mci.__version__,
        timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def tests_payload(junit: Path) -> dict[str, Any]:
    """pytest's JUnit XML reports what failed; passed is what is left over."""
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))

    def total(attr: str) -> int:
        return sum(int(s.get(attr, 0)) for s in suites)

    ran = total("tests")
    failed = total("failures") + total("errors")
    skipped = total("skipped")
    return {"passed": ran - failed - skipped, "failed": failed, "skipped": skipped}


def coverage_payload(report: Path) -> dict[str, Any]:
    """coverage.py's JSON report, reduced to percentages and uncovered lines.

    coverage.py measures statements and branches. It does not measure functions,
    and `percent_covered` is a statement percentage — reporting it a second time
    as a separate `statements` total would dress one reading up as two.
    """
    data = json.loads(report.read_text(encoding="utf-8"))
    totals = data.get("totals", {})

    out: dict[str, Any] = {"totals": {"lines": round(totals.get("percent_covered", 0.0), 1)}}
    branches = totals.get("num_branches") or 0
    if branches:
        covered = totals.get("covered_branches", 0)
        out["totals"]["branches"] = round(100.0 * covered / branches, 1)

    out["files"] = [
        {
            "path": path,
            "lines": round(info.get("summary", {}).get("percent_covered", 0.0), 1),
            "uncovered": info.get("missing_lines", []),
        }
        for path, info in sorted(data.get("files", {}).items())
    ]
    return out


def write(out_dir: Path, record: str, producer: str, payload: dict, *, tracked: bool) -> Path:
    snapshot = mci.Snapshot(
        manifest=mci.Manifest(
            record=record,
            source=source(tracked=tracked),
            producer=producer,
            profile=profile(),
            tracking=mci.Tracking(enabled=tracked, generation=1),
        ),
        payload=payload,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record}.json"
    path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True, help="pytest --junitxml output")
    parser.add_argument("--coverage", type=Path, required=True, help="coverage json report")
    parser.add_argument("--out", type=Path, required=True, help="directory for the snapshots")
    parser.add_argument(
        "--track",
        action="store_true",
        help="Mark the snapshots as project history. Only a push to the "
        "default branch should do this; a pull request must not.",
    )
    args = parser.parse_args(argv)

    written = [
        write(args.out, "tests", "pytest", tests_payload(args.junit), tracked=args.track),
        write(
            args.out, "coverage", "coverage.py", coverage_payload(args.coverage), tracked=args.track
        ),
    ]
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
