"""CLI for validating and persisting CI snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from molcrafts_ci.gate import GateResult
from molcrafts_ci.persist import ingest_snapshot, read_snapshot, snapshot_path
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


def _cmd_validate_gate(args: argparse.Namespace) -> int:
    result = GateResult.model_validate_json(Path(args.path).read_text(encoding="utf-8"))
    _emit({"ok": True, "status": result.status, "gate": result.gate})
    return 0 if result.status != "fail" else 1


def _cmd_ingest(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root)

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
        target = snapshot_path(
            data_root,
            project=args.project,
            record=snap.manifest.record,
            generation=snap.manifest.tracking.generation,
            snapshot_id=snap.snapshot_id(),
        )
        existed = target.exists()
        out = ingest_snapshot(data_root, args.project, snap, if_exists=args.if_exists)
        return {**common, "status": "skipped" if existed else "ingested", "stored": str(out)}

    return _each(args.path, handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="molcrafts-ci")
    sub = parser.add_subparsers(dest="command", required=True)

    p_vs = sub.add_parser("validate-snapshot", help="Validate one or more Snapshot JSON files")
    p_vs.add_argument("path", nargs="+")
    p_vs.set_defaults(func=_cmd_validate_snapshot)

    p_vg = sub.add_parser("validate-gate", help="Validate a GateResult JSON file")
    p_vg.add_argument("path")
    p_vg.set_defaults(func=_cmd_validate_gate)

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

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
