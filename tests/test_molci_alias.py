"""Downstream short import: ``import molci as mci``."""

from __future__ import annotations

import molci as mci


def test_molci_alias_exports_core_types() -> None:
    assert mci.Manifest is not None
    assert mci.Snapshot is not None
    assert mci.GateResult is not None
    assert mci.Tracking is not None
    assert isinstance(mci.__version__, str)


def test_molci_builds_snapshot() -> None:
    snap = mci.Snapshot(
        manifest=mci.Manifest(
            kind="benchmark",
            source=mci.Source(repository="MolCrafts/molpy", commit="abc1234567890"),
            producer="test",
            tracking=mci.Tracking(enabled=False),
        ),
        payload={"ok": True},
    )
    assert snap.snapshot_id().startswith("benchmark-")
