from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from molcrafts_ci.config import Nightly
from molcrafts_ci.release import (
    dist_version,
    file_version,
    nightly_version,
    release_ready,
    stamp_nightly,
    wait_for_ci,
)

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


def test_stamp_nightly_from_a_version_module(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "version.py").write_text('version = "0.19.1"\n', encoding="utf-8")
    nightly = Nightly(
        package="molcrafts-molpy-nightly",
        version_file="version.py",
        rename={"molcrafts-molrs": "molcrafts-molrs-nightly"},
    )
    version = nightly_version(tmp_path, nightly, now=datetime(2026, 10, 23, 3, 37, tzinfo=UTC))
    assert version == "0.19.1.dev202610230337"
    stamp_nightly(tmp_path, nightly, version)
    text = (tmp_path / "pyproject.toml").read_text()
    assert 'name = "molcrafts-molpy-nightly"\nversion = "0.19.1.dev202610230337"\n' in text
    assert "dynamic" not in text
    assert '"molcrafts-molrs-nightly>=0.19.0.dev0"' in text
    assert "tool.uv.sources" not in text
    assert "[tool.ruff]" in text


def test_stamp_nightly_of_a_maturin_package(tmp_path: Path) -> None:
    """molrs: the version comes from Cargo.toml; the package lives in molpy/."""
    (tmp_path / "molpy").mkdir()
    (tmp_path / "molpy/Cargo.toml").write_text(
        '[package]\nname = "molpy"\nversion = "0.19.0"\n', encoding="utf-8"
    )
    (tmp_path / "molpy/pyproject.toml").write_text(
        '[project]\nname = "molcrafts-molpy"\ndynamic = ["version", "readme"]\n'
        '[tool.maturin]\nmodule-name = "molpy._core"\n',
        encoding="utf-8",
    )
    nightly = Nightly(
        package="molcrafts-molpy-nightly",
        pyproject="molpy/pyproject.toml",
        version_file="molpy/Cargo.toml",
    )
    assert nightly_version(tmp_path, nightly).startswith("0.19.0.dev")
    stamp_nightly(tmp_path, nightly, "0.19.0.dev202610230317")
    assert (tmp_path / "molpy/pyproject.toml").read_text() == (
        '[project]\nname = "molcrafts-molpy-nightly"\nversion = "0.19.0.dev202610230317"\n'
        'dynamic = ["readme"]\n[tool.maturin]\nmodule-name = "molpy._core"\n'
    )


def test_stamp_nightly_rejects_an_unknown_rename(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "1.0"\n', encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="nightly.rename: other is not a dependency"):
        stamp_nightly(
            tmp_path, Nightly(package="p-nightly", rename={"other": "other-nightly"}), "1.0.dev1"
        )


def test_release_ready_is_a_dry_run_off_a_tag() -> None:
    logs: list[str] = []
    release_ready(
        "1.0.0", ref="refs/heads/dev", repository="r", sha="s", token="t", log=logs.append
    )
    assert logs == ["refs/heads/dev is not a tag: a dry run, version 1.0.0"]


def test_release_ready_wants_the_tag_to_be_the_version() -> None:
    with pytest.raises(RuntimeError, match="the tag is v1.0.1, the version is 1.0.0"):
        release_ready("1.0.0", ref="refs/tags/v1.0.1", repository="r", sha="s", token="t")


def test_file_version_reads_cargo_and_modules(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[workspace.package]\nversion = "0.19.0"\n')
    (tmp_path / "version.py").write_text('__version__ = "2.1"\n')
    assert file_version(tmp_path / "Cargo.toml") == "0.19.0"
    assert file_version(tmp_path / "version.py") == "2.1"


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
