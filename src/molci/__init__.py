"""Public short import: ``import molci as mci``.

Re-exports the ``molcrafts_ci`` package surface so downstream code can use the
short name while the distribution remains ``molcrafts-ci``.
"""

from molcrafts_ci import (
    GateResult,
    GateStatus,
    Manifest,
    Snapshot,
    SnapshotIndex,
    Source,
    Tracking,
    __version__,
)
from molcrafts_ci.index import ingest_snapshot, read_snapshot, write_snapshot

__all__ = [
    "GateResult",
    "GateStatus",
    "Manifest",
    "Source",
    "Tracking",
    "Snapshot",
    "SnapshotIndex",
    "ingest_snapshot",
    "read_snapshot",
    "write_snapshot",
    "__version__",
]
