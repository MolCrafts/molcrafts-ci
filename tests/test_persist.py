from __future__ import annotations

import pytest

from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.persist import SnapshotIndex, ingest_snapshot
from molcrafts_ci.snapshot import Snapshot


def make_snapshot(*, tracked: bool = True, commit: str = "abc123def456789") -> Snapshot:
    return Snapshot(
        manifest=Manifest(
            record="benchmark",
            source=Source(repository="MolCrafts/molpy", commit=commit),
            producer="pytest-benchmark",
            profile="linux-x86_64",
            tracking=Tracking(enabled=tracked, generation=1),
        ),
        payload={"metrics": {"mean_ns": 12.5}},
    )


class TestIngestSnapshot:
    def test_rejects_a_second_ingest_by_default(self, tmp_path) -> None:
        snap = make_snapshot()
        ingest_snapshot(tmp_path, "molpy", snap)
        with pytest.raises(FileExistsError):
            ingest_snapshot(tmp_path, "molpy", snap)

    def test_skip_makes_a_repeated_ingest_a_no_op(self, tmp_path) -> None:
        """
        The submit action re-runs the ingest on every push attempt, so a
        duplicate must converge rather than append a second history entry.
        """
        snap = make_snapshot()
        first = ingest_snapshot(tmp_path, "molpy", snap)
        again = ingest_snapshot(tmp_path, "molpy", snap, if_exists="skip")

        assert again == first
        entries = list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))
        assert len(entries) == 1

    def test_skip_still_ingests_a_new_snapshot(self, tmp_path) -> None:
        ingest_snapshot(tmp_path, "molpy", make_snapshot(), if_exists="skip")
        ingest_snapshot(tmp_path, "molpy", make_snapshot(commit="fed987"), if_exists="skip")

        assert len(list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))) == 2

    def test_refuses_an_untracked_snapshot(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="tracking.enabled is false"):
            ingest_snapshot(tmp_path, "molpy", make_snapshot(tracked=False))


class TestSnapshotIndexHas:
    def test_reports_membership_per_record(self, tmp_path) -> None:
        snap = make_snapshot()
        ingest_snapshot(tmp_path, "molpy", snap)
        index = SnapshotIndex(tmp_path)

        assert index.has("molpy", "benchmark", snap.snapshot_id())
        assert not index.has("molpy", "coverage", snap.snapshot_id())
        assert not index.has("molrs", "benchmark", snap.snapshot_id())
