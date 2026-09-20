"""CLI for validating and persisting CI snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from molcrafts_ci.gate import GateResult
from molcrafts_ci.persist import ingest_snapshot, read_snapshot
from molcrafts_ci.snapshot import Snapshot


def _cmd_validate_snapshot(args: argparse.Namespace) -> int:
    snap = Snapshot.model_validate_json(Path(args.path).read_text(encoding="utf-8"))
    print(
        json.dumps({"ok": True, "snapshot_id": snap.snapshot_id(), "record": snap.manifest.record})
    )
    return 0


def _cmd_validate_gate(args: argparse.Namespace) -> int:
    result = GateResult.model_validate_json(Path(args.path).read_text(encoding="utf-8"))
    print(json.dumps({"ok": True, "status": result.status, "gate": result.gate}))
    return 0 if result.status != "fail" else 1


def _cmd_ingest(args: argparse.Namespace) -> int:
    snap = read_snapshot(Path(args.path))
    out = ingest_snapshot(Path(args.data_root), args.project, snap)
    print(json.dumps({"ok": True, "path": str(out)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="molcrafts-ci")
    sub = parser.add_subparsers(dest="command", required=True)

    p_vs = sub.add_parser("validate-snapshot", help="Validate a Snapshot JSON file")
    p_vs.add_argument("path")
    p_vs.set_defaults(func=_cmd_validate_snapshot)

    p_vg = sub.add_parser("validate-gate", help="Validate a GateResult JSON file")
    p_vg.add_argument("path")
    p_vg.set_defaults(func=_cmd_validate_gate)

    p_in = sub.add_parser("ingest", help="Persist snapshot + append index (tracking must be on)")
    p_in.add_argument("path", help="Path to Snapshot JSON")
    p_in.add_argument("--project", required=True)
    p_in.add_argument("--data-root", default="data")
    p_in.set_defaults(func=_cmd_ingest)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
