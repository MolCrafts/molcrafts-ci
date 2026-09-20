"""molcrafts-ci - shared CI engineering infrastructure for MolCrafts."""

from molcrafts_ci.gate import GateResult, GateStatus
from molcrafts_ci.index import SnapshotIndex
from molcrafts_ci.manifest import Manifest, Source, Tracking
from molcrafts_ci.snapshot import Snapshot

__all__ = [
    "GateResult",
    "GateStatus",
    "Manifest",
    "Source",
    "Tracking",
    "Snapshot",
    "SnapshotIndex",
]

__version__ = "0.1.0"
