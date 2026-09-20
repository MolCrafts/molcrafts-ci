"""molcrafts-ci - shared CI engineering infrastructure for MolCrafts."""

from importlib.metadata import PackageNotFoundError, version

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

try:
    # pyproject is the single source; nothing here restates it.
    __version__ = version("molcrafts-ci")
except PackageNotFoundError:  # running from a source tree, uninstalled
    __version__ = "0+unknown"
