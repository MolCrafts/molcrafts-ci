from __future__ import annotations

import pytest

from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.persist import SnapshotIndex, ingest_snapshot, read_snapshot, write_snapshot
from molcrafts_ci.snapshot import Snapshot


def make_snapshot(
    *,
    tracked: bool = True,
    commit: str = "abc123def456789",
    observation: str = "campaign-one",
    record: str = "benchmark",
) -> Snapshot:
    return Snapshot(
        manifest=Manifest(
            record=record,
            observation_id=observation if record == "benchmark" else None,
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
        ingest_snapshot(
            tmp_path,
            "molpy",
            make_snapshot(commit="fed987", observation="campaign-two"),
            if_exists="skip",
        )

        assert len(list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))) == 2

    def test_refuses_an_untracked_snapshot(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="tracking.enabled is false"):
            ingest_snapshot(tmp_path, "molpy", make_snapshot(tracked=False))

    def test_recovery_indexes_the_stored_observation(self, tmp_path) -> None:
        original = make_snapshot(record="tests")
        original.manifest.source.workflow_run = 1
        original.manifest.source.timestamp = "2026-01-01T00:00:00Z"
        path = write_snapshot(tmp_path, "molpy", original)
        rerun = make_snapshot(record="tests")
        rerun.manifest.source.workflow_run = 2
        rerun.manifest.source.timestamp = "2026-01-02T00:00:00Z"
        rerun.payload = {"different": True}

        ingest_snapshot(tmp_path, "molpy", rerun, if_exists="skip")

        (entry,) = SnapshotIndex(tmp_path).entries("molpy", "tests")
        assert entry["workflow_run"] == 1
        assert entry["timestamp"] == original.manifest.source.timestamp
        assert read_snapshot(path) == original

    @pytest.mark.parametrize("field", ["project", "record", "profile", "commit"])
    @pytest.mark.parametrize("unsafe", ["../escape", "/escape", r"..\escape", "C:escape"])
    def test_rejects_unsafe_snapshot_components(self, tmp_path, field, unsafe) -> None:
        snap = make_snapshot()
        project = "molpy"
        if field == "project":
            project = unsafe
        elif field == "commit":
            snap.manifest.record = "tests"
            snap.manifest.source.commit = unsafe
        else:
            setattr(snap.manifest, field, unsafe)
        with pytest.raises(ValueError, match="path component"):
            ingest_snapshot(tmp_path, project, snap)
        assert list(tmp_path.iterdir()) == []

    def test_rejects_snapshot_symlink_escape(self, tmp_path) -> None:
        root = tmp_path / "data"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (root / "snapshots").symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError, match="data root"):
            ingest_snapshot(root, "molpy", make_snapshot())
        assert list(outside.iterdir()) == []


class TestSnapshotIndexHas:
    @pytest.mark.parametrize("field", ["project", "record"])
    @pytest.mark.parametrize("unsafe", ["", ".", "..", "../escape", "/escape", r"..\escape"])
    def test_rejects_unsafe_index_components(self, tmp_path, field, unsafe) -> None:
        project, record = (unsafe, "benchmark") if field == "project" else ("molpy", unsafe)
        with pytest.raises(ValueError, match="path component"):
            SnapshotIndex(tmp_path).index_path(project, record)

    def test_rejects_index_symlink_escape(self, tmp_path) -> None:
        root = tmp_path / "data"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (root / "index").symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError, match="data root"):
            SnapshotIndex(root).append("molpy", make_snapshot(), relative_path="snapshot.json")
        assert list(outside.iterdir()) == []

    def test_reports_membership_per_record(self, tmp_path) -> None:
        snap = make_snapshot()
        ingest_snapshot(tmp_path, "molpy", snap)
        index = SnapshotIndex(tmp_path)

        assert index.has("molpy", "benchmark", snap.snapshot_id())
        assert not index.has("molpy", "coverage", snap.snapshot_id())
        assert not index.has("molrs", "benchmark", snap.snapshot_id())


class TestGenerations:
    def test_a_new_generation_of_the_same_commit_is_indexed(self, tmp_path) -> None:
        """Generation 2 is a separate history, even at the same commit."""
        first = make_snapshot()
        second = first.model_copy(
            update={
                "manifest": first.manifest.model_copy(
                    update={"tracking": Tracking(enabled=True, generation=2)}
                )
            }
        )
        ingest_snapshot(tmp_path, "molpy", first, if_exists="skip")
        ingest_snapshot(tmp_path, "molpy", second, if_exists="skip")

        entries = list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))
        assert [(e["generation"], e["snapshot_id"]) for e in entries] == [
            (1, "benchmark-12-linux-x86_64-g1-campaign-one"),
            (2, "benchmark-12-linux-x86_64-g2-campaign-one"),
        ]

    def test_same_commit_campaigns_have_independent_observations(self, tmp_path) -> None:
        first = make_snapshot()
        second = make_snapshot(observation="campaign-two")
        a = ingest_snapshot(tmp_path, "molpy", first)
        b = ingest_snapshot(tmp_path, "molpy", second)
        assert a != b
        entries = list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))
        assert [e["observation_id"] for e in entries] == ["campaign-one", "campaign-two"]
        assert entries[0]["commit"] == entries[1]["commit"]

    @pytest.mark.parametrize("change", ["payload", "source", "provenance"])
    def test_reused_observation_rejects_conflicts_even_when_skipping(
        self, tmp_path, change
    ) -> None:
        original = make_snapshot()
        path = ingest_snapshot(tmp_path, "molpy", original)
        different = make_snapshot()
        if change == "payload":
            different.payload["metrics"]["mean_ns"] = 13
        elif change == "source":
            different.manifest.source.commit = "another-commit"
        else:
            different.manifest.provenance = {"bundle_sha256": "different"}
        with pytest.raises(ValueError, match="conflicting benchmark observation"):
            ingest_snapshot(tmp_path, "molpy", different, if_exists="skip")
        assert read_snapshot(path) == original
        assert len(list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))) == 1

    def test_identical_retry_recovers_a_snapshot_not_yet_indexed(self, tmp_path) -> None:
        snap = make_snapshot()
        write_snapshot(tmp_path, "molpy", snap)
        ingest_snapshot(tmp_path, "molpy", snap, if_exists="skip")
        assert len(list(SnapshotIndex(tmp_path).entries("molpy", "benchmark"))) == 1

    def test_profiles_with_delimiters_cannot_alias_observations(self) -> None:
        first = make_snapshot(observation="x-g1-y")
        second = make_snapshot(observation="y")
        first.manifest.profile = "a"
        second.manifest.profile = "a-g1-x"
        assert first.snapshot_id() != second.snapshot_id()


class TestListing:
    def test_library_ingest_keeps_the_listing_current(self, tmp_path) -> None:
        """The site only sees projects index-listing.json names."""
        import json

        ingest_snapshot(tmp_path, "molpy", make_snapshot())
        listing = json.loads((tmp_path / "index-listing.json").read_text())
        assert listing["indexes"] == ["index/molpy/benchmark.jsonl"]
