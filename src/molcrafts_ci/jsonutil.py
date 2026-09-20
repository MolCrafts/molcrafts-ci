"""Deterministic JSON helpers for Git-friendly CI state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps_deterministic(data: Any, *, indent: int | None = 2) -> str:
    """Serialize with stable key order and consistent formatting.

    Pass ``indent=None`` for a single-line JSONL record (still sorted keys).
    """
    return (
        json.dumps(
            data,
            ensure_ascii=False,
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def loads(text: str) -> Any:
    return json.loads(text)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_deterministic(data), encoding="utf-8")


def read_json(path: Path) -> Any:
    return loads(path.read_text(encoding="utf-8"))
