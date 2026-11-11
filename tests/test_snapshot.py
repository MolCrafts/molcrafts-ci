from __future__ import annotations

import json
from pathlib import Path

import pytest

from molcrafts_ci.jsonutil import dumps_deterministic
from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.persist import SnapshotIndex, ingest_snapshot, write_snapshot
from molcrafts_ci.snapshot import Snapshot


def _snap(*, tracking: bool = True, generation: int = 1) -> Snapshot:
    return Snapshot(
        manifest=Manifest(
            record="benchmark",
            observation_id="campaign-one",
            source=Source(
                repository="MolCrafts/molpy",
                commit="abcdef1234567890",
                ref="refs/heads/master",
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
    assert _snap().snapshot_id() == "benchmark-12-linux-x86_64-g1-campaign-one"


@pytest.mark.parametrize(
    "observation", [None, "", ".", "..", "../x", "a/b", "a\\b", "C:x", "a\x00b"]
)
def test_benchmark_requires_safe_observation_id(observation) -> None:
    manifest = _snap().manifest.model_dump()
    manifest["observation_id"] = observation
    with pytest.raises(ValueError):
        Manifest.model_validate(manifest)


@pytest.mark.parametrize("record", ["tests", "coverage"])
def test_other_records_keep_commit_identity(record) -> None:
    snap = _snap()
    snap.manifest.record = record
    snap.manifest.observation_id = None
    assert snap.snapshot_id() == f"{record}-linux-x86_64-abcdef123456"


def test_refuse_persist_when_tracking_disabled(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tracking.enabled is false"):
        write_snapshot(tmp_path, "molpy", _snap(tracking=False))


def test_ingest_writes_snapshot_and_index(tmp_path: Path) -> None:
    snap = _snap()
    path = ingest_snapshot(tmp_path, "molpy", snap)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["manifest"]["record"] == "benchmark"
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
