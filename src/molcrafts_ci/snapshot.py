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
        """Stable filename stem derived from source + record + profile."""
        m = self.manifest
        short = m.source.commit[:12]
        return f"{m.record}-{m.profile}-{short}"
