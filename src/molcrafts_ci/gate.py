"""Gate evaluation result (not a GitHub Check Run)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GateStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class GateResult(BaseModel):
    """Structured outcome of a domain Gate against a Policy."""

    model_config = ConfigDict(extra="forbid")

    status: GateStatus
    gate: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)
