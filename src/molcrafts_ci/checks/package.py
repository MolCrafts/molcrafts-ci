#!/usr/bin/env python3
"""Inspect the exact tested wheel and host sdist before any publication."""

from __future__ import annotations

import email
import sys
import tarfile
import zipfile
from pathlib import Path

from versions import load


def main() -> int:
    expected = load("Cargo.toml")["workspace"]["package"]["version"]
    wheel, sdist = map(Path, sys.argv[1:])
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("wheel must contain exactly one METADATA")
        message = email.message_from_bytes(archive.read(metadata[0]))
        if message["Name"] != "molcrafts-molpy" or message["Version"] != expected:
            raise ValueError("tested wheel name/version differs from workspace")
        for required in ("molpy/py.typed", "molpy/_core.pyi"):
            if required not in names:
                raise ValueError(f"tested wheel misses {required}")
        if not any("license" in n.lower() for n in names):
            raise ValueError("tested wheel misses its license")
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        for required in (
            "molpy/Cargo.toml",
            "crates/molrs/Cargo.toml",
            "pyproject.toml",
        ):
            if not any(n.endswith("/" + required) for n in names):
                raise ValueError(f"sdist misses {required}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
