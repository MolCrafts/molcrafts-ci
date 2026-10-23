"""Snapshot envelope: Manifest + opaque domain Payload."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from molcrafts_ci.manifest import Manifest


class Snapshot(BaseModel):
    """Immutable CI-observed engineering state.

    ``molcrafts-ci`` understands :attr:`manifest` only. The ``payload`` is an
    opaque, domain-owned document and MUST NOT be interpreted here.
    """

    model_config = ConfigDict(extra="forbid")

    manifest: Manifest
    payload: dict[str, Any] = Field(default_factory=dict)

    def snapshot_id(self) -> str:
        """Stable id from record, profile, generation and commit.

        Generation 1 is left out, so ids published before generations were
        told apart keep their meaning; a later generation of the same commit
        is a different snapshot (`tests-default-g2-abc123def456`).
        """
        m = self.manifest
        short = m.source.commit[:12]
        generation = m.tracking.generation
        tag = "" if generation == 1 else f"g{generation}-"
        return f"{m.record}-{m.profile}-{tag}{short}"
