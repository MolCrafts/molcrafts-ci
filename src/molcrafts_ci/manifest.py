"""Manifest and tracking metadata for CI snapshots."""

from __future__ import annotations

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


class Manifest(BaseModel):
    """Infrastructure metadata describing a snapshot. Domains own the payload."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    kind: str
    source: Source
    producer: str
    profile: str = "default"
    tracking: Tracking = Field(default_factory=Tracking)
    provenance: dict[str, Any] = Field(default_factory=dict)
