#!/usr/bin/env python3
"""Install locked Python/Node dependencies and the pinned actionlint binary."""

from __future__ import annotations

import hashlib
import io
import platform
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.7.12"


def actionlint() -> Path:
    system = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}[platform.system()]
    arch = {"x86_64": "amd64", "AMD64": "amd64", "aarch64": "arm64", "arm64": "arm64"}[
        platform.machine()
    ]
    suffix = "zip" if system == "windows" else "tar.gz"
    name = f"actionlint_{VERSION}_{system}_{arch}.{suffix}"
    target = ROOT / ".tools" / ("actionlint.exe" if system == "windows" else "actionlint")
    stamp = target.with_suffix(".version")
    if target.is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8") == VERSION:
        return target
    release = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/"
    with urllib.request.urlopen(release + name, timeout=60) as response:
        data = response.read()
    with urllib.request.urlopen(
        release + f"actionlint_{VERSION}_checksums.txt", timeout=60
    ) as response:
        checksums = dict(
            line.split()[::-1] for line in response.read().decode("utf-8").splitlines()
        )
    if hashlib.sha256(data).hexdigest() != checksums[name]:
        raise ValueError("actionlint archive checksum mismatch")
    target.parent.mkdir(exist_ok=True)
    if suffix == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            target.write_bytes(archive.read(target.name))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            member = archive.extractfile(target.name)
            if member is None:
                raise ValueError("actionlint archive lacks executable")
            target.write_bytes(member.read())
    target.chmod(0o755)
    stamp.write_text(VERSION, encoding="utf-8")
    return target


if __name__ == "__main__":
    import shutil

    subprocess.run(["uv", "sync", "--locked", "--extra", "dev"], cwd=ROOT, check=True)
    subprocess.run([shutil.which("npm") or "npm", "ci", "--prefix", "site"], cwd=ROOT, check=True)
    print(actionlint())
    subprocess.run(["uvx", "pre-commit", "install"], cwd=ROOT, check=True)
