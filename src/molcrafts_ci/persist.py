"""Git-friendly persistence for snapshots and the SnapshotIndex."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from molcrafts_ci.jsonutil import dumps_deterministic, read_json, write_json
from molcrafts_ci.snapshot import Snapshot


def _data_path(root: Path, *parts: str, suffix: str) -> Path:
    """Keep portable path components and existing symlinks inside the data root."""
    for part in parts:
        if part in ("", ".", "..") or any(char in part for char in "/\\:\0"):
            raise ValueError(f"unsafe path component: {part!r}")
    path = root.joinpath(*parts)
    path = path.with_name(path.name + suffix)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes the data root: {path}")
    return path


def snapshot_path(
    root: Path,
    *,
    project: str,
    record: str,
    generation: int,
    snapshot_id: str,
) -> Path:
    return _data_path(
        root, "snapshots", project, record, str(generation), snapshot_id, suffix=".json"
    )


IfExists = Literal["fail", "skip"]


def write_snapshot(
    root: Path,
    project: str,
    snapshot: Snapshot,
    *,
    if_exists: IfExists = "fail",
) -> Path:
    """Persist an immutable snapshot file.

    A snapshot id is derived from its source, so the same CI commit re-running
    produces the same path. ``if_exists="fail"`` keeps that collision loud;
    ``if_exists="skip"`` returns the existing path untouched, which is what a
    retried or concurrent ingest needs — the file is immutable, so the one
    already on disk remains the authoritative observation, even for a rerun.
    """
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
        if if_exists == "skip":
            return path
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
        return _data_path(self.root, "index", project, record, suffix=".jsonl")

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

    def has(self, project: str, record: str, snapshot_id: str) -> bool:
        """Whether this snapshot is already indexed."""
        return any(e.get("snapshot_id") == snapshot_id for e in self.entries(project, record))

    def entries(self, project: str, record: str) -> Iterator[dict[str, Any]]:
        path = self.index_path(project, record)
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


def write_index_listing(data_root: Path) -> Path:
    """Publish the set of index files, so a reader needs no directory listing.

    The site fetches the index over plain HTTP, where there is nothing to
    enumerate: it has to be told what exists. ``published`` is each project's
    newest index timestamp, so the site can open on whatever ran last without
    fetching every ``*.jsonl``. Rewritten from the tree on every ingest, so it
    stays right when a record is removed or an earlier run half-finished.
    """
    index = SnapshotIndex(data_root)
    listing: list[str] = []
    published: dict[str, str] = {}
    for path in sorted((data_root / "index").glob("*/*.jsonl")):
        project, record = path.parent.name, path.stem
        listing.append(path.relative_to(data_root).as_posix())
        stamps = [e.get("timestamp") for e in index.entries(project, record)]
        stamps = [s for s in stamps if isinstance(s, str)]
        if stamps and max(stamps) > published.get(project, ""):
            published[project] = max(stamps)
    path = data_root / "index-listing.json"
    write_json(path, {"indexes": listing, "published": published})
    return path


def ingest_snapshot(
    data_root: Path,
    project: str,
    snapshot: Snapshot,
    *,
    if_exists: IfExists = "fail",
) -> Path:
    """Write the immutable snapshot, index it and refresh ``index-listing.json``.

    Tracking must be on. Idempotent under ``if_exists="skip"``: the index entry
    is appended only when this snapshot is not indexed yet, so re-running the
    call converges instead of growing a duplicate history.
    """
    snap_path = write_snapshot(data_root, project, snapshot, if_exists=if_exists)
    rel = snap_path.relative_to(data_root).as_posix()
    index = SnapshotIndex(data_root)
    if not index.has(project, snapshot.manifest.record, snapshot.snapshot_id()):
        index.append(project, read_snapshot(snap_path), relative_path=rel)
    write_index_listing(data_root)
    return snap_path
