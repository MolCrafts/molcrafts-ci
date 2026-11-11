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
        """Benchmark identity is profile + generation + observation, never commit.

        A length-prefixed profile keeps benchmark fields unambiguous even when
        profiles and observation IDs contain hyphens. Other records retain
        their commit-based identity and omit generation 1.
        """
        m = self.manifest
        if m.record == "benchmark":
            # Models are mutable; revalidate before constructing a storage key.
            m = Manifest.model_validate(m.model_dump())
            return (
                f"benchmark-{len(m.profile)}-{m.profile}"
                f"-g{m.tracking.generation}-{m.observation_id}"
            )
        short = m.source.commit[:12]
        generation = m.tracking.generation
        tag = "" if generation == 1 else f"g{generation}-"
        return f"{m.record}-{m.profile}-{tag}{short}"
