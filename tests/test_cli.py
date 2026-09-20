from __future__ import annotations

import json
from pathlib import Path

from molcrafts_ci.cli import main
from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.snapshot import Snapshot


def test_cli_validate_and_ingest(tmp_path: Path, capsys) -> None:
    snap = Snapshot(
        manifest=Manifest(
            kind="molrec",
            source=Source(repository="MolCrafts/molcrafts-molrec", commit="deadbeefcafebabe"),
            producer="molrec",
            tracking=Tracking(enabled=True, generation=1),
        ),
        payload={"schema_version": "0.1"},
    )
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text(snap.model_dump_json(indent=2), encoding="utf-8")
    data_root = tmp_path / "data"

    assert main(["validate-snapshot", str(snap_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True

    assert (
        main(
            [
                "ingest",
                str(snap_path),
                "--project",
                "molcrafts-molrec",
                "--data-root",
                str(data_root),
            ]
        )
        == 0
    )
    assert any(data_root.rglob("*.json"))
    assert any(data_root.rglob("*.jsonl"))
