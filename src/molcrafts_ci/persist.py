"""Git-friendly persistence for snapshots and the SnapshotIndex."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from molcrafts_ci.jsonutil import dumps_deterministic, read_json, write_json
from molcrafts_ci.snapshot import Snapshot


def snapshot_path(
    root: Path,
    *,
    project: str,
    record: str,
    generation: int,
    snapshot_id: str,
) -> Path:
    return root / "snapshots" / project / record / str(generation) / f"{snapshot_id}.json"


def write_snapshot(root: Path, project: str, snapshot: Snapshot) -> Path:
    """Persist an immutable snapshot file. Refuses to overwrite."""
    if not snapshot.manifest.tracking.enabled:
        raise ValueError(
            "refusing to persist: tracking.enabled is false "
            "(use workflow artifacts for transient snapshots)"
        )
    path = snapshot_path(
        root,
        project=project,
        record=snapshot.manifest.record,
        generation=snapshot.manifest.tracking.generation,
        snapshot_id=snapshot.snapshot_id(),
    )
    if path.exists():
        raise FileExistsError(f"snapshot already exists: {path}")
    write_json(path, snapshot.model_dump(mode="json"))
    return path


def read_snapshot(path: Path) -> Snapshot:
    return Snapshot.model_validate(read_json(path))


class SnapshotIndex:
    """Append-friendly JSONL index of tracked snapshots."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def index_path(self, project: str, record: str) -> Path:
        return self.root / "index" / project / f"{record}.jsonl"

    def append(self, project: str, snapshot: Snapshot, *, relative_path: str) -> Path:
        if not snapshot.manifest.tracking.enabled:
            raise ValueError("refusing to index: tracking.enabled is false")
        path = self.index_path(project, snapshot.manifest.record)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "snapshot_id": snapshot.snapshot_id(),
            "path": relative_path,
            "record": snapshot.manifest.record,
            "generation": snapshot.manifest.tracking.generation,
            "profile": snapshot.manifest.profile,
            "repository": snapshot.manifest.source.repository,
            "commit": snapshot.manifest.source.commit,
            "ref": snapshot.manifest.source.ref,
            "workflow_run": snapshot.manifest.source.workflow_run,
            "producer": snapshot.manifest.producer,
            "timestamp": snapshot.manifest.source.timestamp,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(dumps_deterministic(entry, indent=None))
        return path

    def entries(self, project: str, record: str) -> Iterator[dict[str, Any]]:
        path = self.index_path(project, record)
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


def ingest_snapshot(data_root: Path, project: str, snapshot: Snapshot) -> Path:
    """Write immutable snapshot and append an index entry (tracking must be on)."""
    snap_path = write_snapshot(data_root, project, snapshot)
    rel = snap_path.relative_to(data_root).as_posix()
    SnapshotIndex(data_root).append(project, snapshot, relative_path=rel)
    return snap_path
