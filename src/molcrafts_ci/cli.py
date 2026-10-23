"""`molci`: run a repository's checks, and build, validate and ingest snapshots.

`check`, `partners`, `plan`, `rust`, `release-ready` and `nightly` talk to
a person; `validate-snapshot`, `ingest` and `snapshot` print
one JSON object per line, for actions/submit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from molcrafts_ci import config as ci_config
from molcrafts_ci import plan, release, run, workspace
from molcrafts_ci.manifest import Manifest, Tracking
from molcrafts_ci.persist import SnapshotIndex, ingest_snapshot, read_snapshot
from molcrafts_ci.producers import (
    COVERAGE_FORMATS,
    detect_profile,
    github_source,
    read_cargo_test,
    read_coverage,
    read_junit,
)
from molcrafts_ci.report import render_report
from molcrafts_ci.snapshot import Snapshot


def _emit(record: dict[str, Any]) -> None:
    """One JSON object per line, so a multi-file run stays machine-readable."""
    print(json.dumps(record))


def _each(paths: Iterable[str], handle) -> int:
    """Run ``handle`` over every path, reporting all failures rather than the first.

    A CI run that produced four snapshots should say which of them is broken in
    one go; stopping at the first sends the operator round the loop four times.
    """
    failed = False
    for raw in paths:
        path = Path(raw)
        try:
            _emit(handle(path))
        except Exception as exc:  # noqa: BLE001 — CLI boundary
            failed = True
            print(
                json.dumps({"ok": False, "path": str(path), "error": str(exc)}),
                file=sys.stderr,
            )
    return 2 if failed else 0


def _cmd_validate_snapshot(args: argparse.Namespace) -> int:
    def handle(path: Path) -> dict[str, Any]:
        snap = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "path": str(path),
            "snapshot_id": snap.snapshot_id(),
            "record": snap.manifest.record,
            "profile": snap.manifest.profile,
            # The submit action reads this to decide whether the run has
            # anything to push; without it the caller has to parse the
            # snapshot a second time in shell.
            "tracking": snap.manifest.tracking.enabled,
            "generation": snap.manifest.tracking.generation,
        }

    return _each(args.path, handle)


def _cmd_ingest(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root)
    index = SnapshotIndex(data_root)

    def handle(path: Path) -> dict[str, Any]:
        snap = read_snapshot(path)
        common = {
            "ok": True,
            "path": str(path),
            "snapshot_id": snap.snapshot_id(),
            "record": snap.manifest.record,
        }
        if args.skip_untracked and not snap.manifest.tracking.enabled:
            # Not an error: an untracked snapshot is a deliberate transient,
            # and its producer still wants the rest of the run to go green.
            return {**common, "status": "untracked"}
        # The index is the published history, so "already there" means indexed,
        # not merely a file on disk.
        indexed = index.has(args.project, snap.manifest.record, snap.snapshot_id())
        out = ingest_snapshot(data_root, args.project, snap, if_exists=args.if_exists)
        return {**common, "status": "skipped" if indexed else "ingested", "stored": str(out)}

    return _each(args.path, handle)


def _cmd_snapshot(args: argparse.Namespace) -> int:
    if args.junit and args.cargo_test:
        raise ValueError("pass one tests report, not both --junit and --cargo-test")
    if not args.junit and not args.cargo_test and not args.coverage:
        raise ValueError("nothing to build: pass --junit, --cargo-test, and/or --coverage")

    source = github_source(require_commit=args.track)
    profile = args.profile or detect_profile()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    def build(record: str, producer: str, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot = Snapshot(
            manifest=Manifest(
                record=record,
                source=source,
                producer=producer,
                profile=profile,
                tracking=Tracking(enabled=args.track, generation=args.generation),
            ),
            payload=payload,
        )
        path = out_dir / f"{record}.json"
        path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return {
            "ok": True,
            "record": record,
            "path": str(path),
            "snapshot_id": snapshot.snapshot_id(),
            "tracking": args.track,
        }

    if args.junit:
        payload = read_junit(Path(args.junit))
        _emit(build(args.tests_record, args.tests_producer or "pytest", payload))
    if args.cargo_test:
        payload = read_cargo_test(Path(args.cargo_test))
        _emit(build(args.tests_record, args.tests_producer or "cargo-test", payload))
    if args.coverage:
        root = Path(args.source_root).resolve()
        payload = read_coverage(Path(args.coverage), fmt=args.coverage_format, source_root=root)
        _emit(build("coverage", args.coverage_producer, payload))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    markdown = render_report(
        title=args.title,
        junit=Path(args.junit) if args.junit else None,
        cargo_test=Path(args.cargo_test) if args.cargo_test else None,
        coverage=Path(args.coverage) if args.coverage else None,
        coverage_format=args.coverage_format,
    )
    print(markdown)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    config = ci_config.load(root)
    checks = run.select(config, args.name, args.stage)
    return run.run_checks(root, config, checks, python=args.python or None)


def _cmd_plan(args: argparse.Namespace) -> int:
    config = ci_config.load(Path(args.root))
    stages = ("release",) if args.release else ("pre-commit", "pre-push")
    rows = plan.legs(config, _github_event(), stages=stages)
    print(f"checks={json.dumps(rows)}")
    for row in rows:
        print(f"  {row['name']} on {row['runs-on']}", file=sys.stderr)
    return 0


def _github_event() -> plan.Event:
    env = os.environ
    pr_head = ""
    event_path = env.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).is_file():
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        head = (payload.get("pull_request") or {}).get("head") or {}
        pr_head = ((head.get("repo") or {}).get("full_name")) or ""
    return plan.Event(
        owner=env.get("GITHUB_REPOSITORY_OWNER", ""),
        repository=env.get("GITHUB_REPOSITORY", ""),
        name=env.get("GITHUB_EVENT_NAME", ""),
        ref=env.get("GITHUB_REF", ""),
        pr_head=pr_head,
    )


def _cmd_partners(args: argparse.Namespace) -> int:
    root = Path(args.root)
    config = ci_config.load(root)
    if not config.partners:
        workspace.stderr("no [partners] in .github/ci.toml; dependencies resolve normally")
        return 0
    workspace.fetch(root, config, log=workspace.stderr)
    return 0


def _cmd_rust(args: argparse.Namespace) -> int:
    root = Path(args.root)
    workspaces = workspace.rust_toolchains(root, ci_config.load(root), log=workspace.stderr)
    print("workspaces<<EOF")
    print("\n".join(workspaces))
    print("EOF")
    return 0


def _cmd_release_ready(args: argparse.Namespace) -> int:
    if args.dist:
        version = release.dist_version(Path(args.dist))
    elif args.version_file:
        version = release.file_version(Path(args.version_file))
    else:
        version = args.version
    release.release_ready(
        version,
        ref=os.environ.get("GITHUB_REF", ""),
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        sha=os.environ.get("GITHUB_SHA", ""),
        token=os.environ.get("GITHUB_TOKEN", ""),
        log=workspace.stderr,
    )
    return 0


def _cmd_nightly(args: argparse.Namespace) -> int:
    root = Path(args.root)
    config = ci_config.load(root)
    if config.nightly is None:
        raise ci_config.ConfigError(f"{config.path}: no [nightly] table")
    if args.print_version:
        print(release.nightly_version(root, config.nightly))
        return 0
    version = args.version or release.nightly_version(root, config.nightly)
    release.stamp_nightly(root, config.nightly, version)
    print(version)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="molci")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ck = sub.add_parser("check", help="Run checks from .github/ci.toml")
    p_ck.add_argument("name", nargs="*", help="Checks to run (default: all but release)")
    p_ck.add_argument("--stage", choices=ci_config.STAGES, help="Run every check of a stage")
    p_ck.add_argument("--python", help="Python for uv to use (sets UV_PYTHON)")
    p_ck.add_argument("--root", default=".", help="Repository root (default: .)")
    p_ck.set_defaults(func=_cmd_check)

    p_pl = sub.add_parser("plan", help="CI: the jobs of this run, as a GitHub output line")
    p_pl.add_argument("--release", action="store_true", help="Plan the release-stage checks")
    p_pl.add_argument("--root", default=".")
    p_pl.set_defaults(func=_cmd_plan)

    p_pa = sub.add_parser("partners", help="Clone missing [partners] next to this repository")
    p_pa.add_argument("--root", default=".")
    p_pa.set_defaults(func=_cmd_partners)

    p_ru = sub.add_parser("rust", help="CI: install pinned Rust toolchains, list cargo workspaces")
    p_ru.add_argument("--root", default=".")
    p_ru.set_defaults(func=_cmd_rust)

    p_rr = sub.add_parser(
        "release-ready",
        help="Release: on a v* tag, the tag is the version, is on master, and ci passed",
    )
    version_of = p_rr.add_mutually_exclusive_group(required=True)
    version_of.add_argument("--dist", help="Directory of the built wheel and sdist")
    version_of.add_argument("--version-file", help="A Cargo.toml, pyproject.toml or version file")
    version_of.add_argument("--version", help="The version itself")
    p_rr.set_defaults(func=_cmd_release_ready)

    p_ni = sub.add_parser("nightly", help="Nightly: rename the [nightly] package and version it")
    p_ni.add_argument("--version", help="Use this version (one for every OS of a nightly)")
    p_ni.add_argument("--print-version", action="store_true", help="Only print the nightly version")
    p_ni.add_argument("--root", default=".")
    p_ni.set_defaults(func=_cmd_nightly)

    p_vs = sub.add_parser("validate-snapshot", help="Validate one or more Snapshot JSON files")
    p_vs.add_argument("path", nargs="+")
    p_vs.set_defaults(func=_cmd_validate_snapshot)

    p_in = sub.add_parser("ingest", help="Persist snapshot + append index (tracking must be on)")
    p_in.add_argument("path", nargs="+", help="Path to Snapshot JSON")
    p_in.add_argument("--project", required=True)
    p_in.add_argument("--data-root", default="data")
    p_in.add_argument(
        "--if-exists",
        choices=["fail", "skip"],
        default="fail",
        help="What to do when the snapshot is already stored (default: fail)",
    )
    p_in.add_argument(
        "--skip-untracked",
        action="store_true",
        help="Report untracked snapshots instead of failing on them",
    )
    p_in.set_defaults(func=_cmd_ingest)

    p_sn = sub.add_parser(
        "snapshot",
        help="Build tests/coverage Snapshots from a test run's native output",
    )
    p_sn.add_argument("--out", required=True, help="Directory to write the snapshots into")
    p_sn.add_argument("--junit", help="JUnit XML from pytest --junitxml")
    p_sn.add_argument(
        "--cargo-test",
        help="Log from cargo test, the run whose 'test result:' lines are the totals",
    )
    p_sn.add_argument("--coverage", help="Coverage report; see --coverage-format")
    p_sn.add_argument(
        "--coverage-format",
        choices=COVERAGE_FORMATS,
        default="auto",
        help="coverage.py JSON or an LCOV tracefile (default: LCOV for .info/.lcov)",
    )
    p_sn.add_argument(
        "--tests-producer",
        help="Producer name stored on the tests snapshot (default: pytest or cargo-test)",
    )
    p_sn.add_argument(
        "--tests-record",
        default="tests",
        help="Record name of the tests snapshot (default: tests), e.g. conformance",
    )
    p_sn.add_argument("--coverage-producer", default="coverage.py")
    p_sn.add_argument("--profile", help="Override the detected <os>-<arch> profile")
    p_sn.add_argument(
        "--source-root",
        default=".",
        help="Strip this prefix from coverage file paths (default: the working "
        "directory), so a snapshot records repo paths and not the runner's layout",
    )
    p_sn.add_argument("--generation", type=int, default=1)
    p_sn.add_argument(
        "--track",
        action="store_true",
        help="Mark the snapshots as project history. Only a push to the default "
        "branch should do this; a pull request must not.",
    )
    p_sn.set_defaults(func=_cmd_snapshot)

    p_rp = sub.add_parser(
        "report",
        help="Write a test run's counts and coverage as a markdown table (never gates)",
    )
    p_rp.add_argument("--title", required=True, help="Heading above the table, e.g. the job name")
    tests_in = p_rp.add_mutually_exclusive_group()
    tests_in.add_argument("--junit", help="JUnit XML from pytest --junitxml")
    tests_in.add_argument("--cargo-test", help="Log from cargo test")
    p_rp.add_argument("--coverage", help="Coverage report; see --coverage-format")
    p_rp.add_argument(
        "--coverage-format",
        choices=COVERAGE_FORMATS,
        default="auto",
        help="coverage.py JSON or an LCOV tracefile (default: LCOV for .info/.lcov)",
    )
    p_rp.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        if args.command in JSON_COMMANDS:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        else:
            print(f"molci {args.command}: {exc}", file=sys.stderr)
        return 2


JSON_COMMANDS = {"validate-snapshot", "ingest", "snapshot"}


if __name__ == "__main__":
    raise SystemExit(main())
