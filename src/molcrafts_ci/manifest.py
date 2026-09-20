"""Manifest and tracking metadata for CI snapshots."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Tracking(BaseModel):
    """Controls whether a snapshot becomes persistent project history."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    generation: int = Field(default=1, ge=1)


class Source(BaseModel):
    """Provenance sufficient to trace a snapshot back to a CI execution."""

    model_config = ConfigDict(extra="forbid")

    repository: str
    commit: str
    ref: str | None = None
    workflow_run: int | None = None
    run_attempt: int | None = None
    producer_version: str | None = None
    timestamp: str | None = None


def schema_version() -> str:
    """
    The schema version, taken from the package's minor.

    The shape of a manifest and the release that defines it move together, so
    there is nothing to keep in step by hand — bumping the minor *is* bumping
    the schema.

    Caveat for 1.0: while the project is 0.x the minor is the breaking-change
    axis, so it works. Once major becomes that axis this has to follow major
    instead, or 1.0.0 would emit "0" and read as a step backwards.
    """
    try:
        return version("molcrafts-ci").split(".")[1]
    except PackageNotFoundError:  # running from a source tree, uninstalled
        return "0"


class Manifest(BaseModel):
    """Infrastructure metadata describing a snapshot. Domains own the payload."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default_factory=lambda: schema_version())
    record: str
    source: Source
    producer: str
    profile: str = "default"
    tracking: Tracking = Field(default_factory=Tracking)
    provenance: dict[str, Any] = Field(default_factory=dict)
