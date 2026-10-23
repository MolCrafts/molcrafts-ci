from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from molcrafts_ci.config import Nightly
from molcrafts_ci.release import dist_version, stamp_nightly, wait_for_ci

PYPROJECT = """[project]
name = "molcrafts-molpy"
dynamic = ["version"]
dependencies = [
    "numpy>=2.0",
    "molcrafts-molrs>=0.19.0,<0.20",
]

[tool.uv.sources]
molcrafts-molrs = { path = "../molrs/molrs-python" }

[tool.ruff]
line-length = 100
"""


def test_stamp_nightly(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "version.py").write_text('version = "0.19.1"\n', encoding="utf-8")
    nightly = Nightly(
        package="molcrafts-molpy-nightly",
        version_file="version.py",
        rename={"molcrafts-molrs": "molcrafts-molrs-nightly"},
    )
    version = stamp_nightly(tmp_path, nightly, now=datetime(2026, 10, 23, 3, 37, tzinfo=UTC))
    assert version == "0.19.1.dev202610230337"
    assert (tmp_path / "version.py").read_text() == 'version = "0.19.1.dev202610230337"\n'
    text = (tmp_path / "pyproject.toml").read_text()
    assert 'name = "molcrafts-molpy-nightly"' in text
    assert '"molcrafts-molrs-nightly>=0.19.0.dev0"' in text
    assert "tool.uv.sources" not in text
    assert "[tool.ruff]" in text


def test_stamp_nightly_rejects_an_unknown_rename(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "1.0"\n', encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="nightly.rename: other is not a dependency"):
        stamp_nightly(tmp_path, Nightly(package="p-nightly", rename={"other": "other-nightly"}))


def test_dist_version(tmp_path: Path) -> None:
    (tmp_path / "molcrafts_molpy-0.19.1-py3-none-any.whl").touch()
    (tmp_path / "molcrafts_molpy-0.19.1.tar.gz").touch()
    assert dist_version(tmp_path) == "0.19.1"
    (tmp_path / "molcrafts_molpy-0.19.2.tar.gz").touch()
    with pytest.raises(RuntimeError, match="2 versions"):
        dist_version(tmp_path)


def ci(status: str, conclusion: str | None, created: str = "1") -> dict:
    return {
        "status": status,
        "conclusion": conclusion,
        "created_at": created,
        "html_url": "https://github.com/MolCrafts/molpy/actions/runs/1",
    }


def test_wait_for_ci_waits_for_the_run_then_passes() -> None:
    answers = iter([[], [ci("in_progress", None)], [ci("completed", "success")]])
    sleeps: list[float] = []
    wait_for_ci(
        "MolCrafts/molpy",
        "a" * 40,
        "t",
        runs=lambda *_: next(answers),
        sleep=sleeps.append,
        log=lambda _: None,
    )
    assert len(sleeps) == 2


def test_wait_for_ci_reads_the_newest_run() -> None:
    """A re-run that passed counts; the failed attempt before it does not."""
    history = [ci("completed", "failure", "1"), ci("completed", "success", "2")]
    wait_for_ci("MolCrafts/molpy", "a" * 40, "t", runs=lambda *_: history, log=lambda _: None)


def test_wait_for_ci_fails_on_a_failed_run() -> None:
    with pytest.raises(RuntimeError, match="ci failure: https://"):
        wait_for_ci(
            "MolCrafts/molpy",
            "a" * 40,
            "t",
            runs=lambda *_: [ci("completed", "failure")],
            log=lambda _: None,
        )
