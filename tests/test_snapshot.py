from __future__ import annotations

import json
from pathlib import Path

import pytest

from molcrafts_ci.gate import GateResult, GateStatus
from molcrafts_ci.jsonutil import dumps_deterministic
from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.persist import SnapshotIndex, ingest_snapshot, write_snapshot
from molcrafts_ci.snapshot import Snapshot


def _snap(*, tracking: bool = True, generation: int = 1) -> Snapshot:
    return Snapshot(
        manifest=Manifest(
            kind="benchmark",
            source=Source(
                repository="MolCrafts/molpy",
                commit="abcdef1234567890",
                ref="refs/heads/main",
                workflow_run=42,
                timestamp="2026-09-20T12:00:00Z",
            ),
            producer="pytest-benchmark",
            profile="linux-x86_64",
            tracking=Tracking(enabled=tracking, generation=generation),
        ),
        payload={"metrics": {"mean_ns": 12.5}},
    )


def test_deterministic_json_sorts_keys() -> None:
    text = dumps_deterministic({"b": 1, "a": {"z": 2, "y": 3}})
    assert text.index('"a"') < text.index('"b"')
    assert text.endswith("\n")


def test_snapshot_id() -> None:
    assert _snap().snapshot_id() == "benchmark-linux-x86_64-abcdef123456"


def test_refuse_persist_when_tracking_disabled(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tracking.enabled is false"):
        write_snapshot(tmp_path, "molpy", _snap(tracking=False))


def test_ingest_writes_snapshot_and_index(tmp_path: Path) -> None:
    snap = _snap()
    path = ingest_snapshot(tmp_path, "molpy", snap)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["manifest"]["kind"] == "benchmark"
    assert loaded["payload"]["metrics"]["mean_ns"] == 12.5

    entries = list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))
    assert len(entries) == 1
    assert entries[0]["commit"] == "abcdef1234567890"
    assert entries[0]["generation"] == 1


def test_immutable_snapshot_no_overwrite(tmp_path: Path) -> None:
    snap = _snap()
    write_snapshot(tmp_path, "molpy", snap)
    with pytest.raises(FileExistsError):
        write_snapshot(tmp_path, "molpy", snap)


def test_gate_result_status() -> None:
    result = GateResult(
        status=GateStatus.FAIL,
        gate="performance-regression",
        summary="mean_ns exceeded policy",
        details={"delta": 0.2},
        references=["snapshot:abcdef123456"],
    )
    assert result.model_dump(mode="json")["status"] == "fail"
