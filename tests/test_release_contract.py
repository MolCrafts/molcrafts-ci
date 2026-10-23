"""The release.toml contract of the previous CI scheme (actions/check-workflows)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "actions/check-workflows/release_contract.py"
_SPEC = importlib.util.spec_from_file_location("release_contract", _PATH)
release = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = release
_SPEC.loader.exec_module(release)


def write(tmp_path: Path, text: str) -> Path:
    (tmp_path / ".github").mkdir(exist_ok=True)
    (tmp_path / ".github/release.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_a_stable_target_names_its_file_and_environment() -> None:
    pypi = release.target("pypi")
    assert (pypi.workflow_file, pypi.environment, pypi.trusted) == ("release.yml", "pypi", "pypi")
    assert release.target("vscode-marketplace").secrets == ("VSCE_PAT", "OVSX_PAT")
    assert release.target("github-release").environment is None


def test_a_nightly_twin_publishes_from_nightly_through_its_own_environment() -> None:
    twin = release.target("pypi-nightly")
    assert (twin.workflow_file, twin.environment, twin.trusted) == (
        "nightly.yml",
        "pypi-nightly",
        "pypi",
    )
    pages = release.target("cloudflare-pages-nightly")
    assert (pages.workflow_file, pages.environment) == ("nightly.yml", "cloudflare-pages-nightly")
    assert pages.secrets == ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")


@pytest.mark.parametrize("name", ["anaconda", "release-core", "pypi-nightly-nightly"])
def test_an_unknown_target_is_refused(name: str) -> None:
    assert not release.known(name)
    with pytest.raises(KeyError, match="not a publishing target"):
        release.target(name)


def test_read_release(tmp_path: Path) -> None:
    assert release.read_release(tmp_path) is None
    root = write(tmp_path, '[npm]\npackages = ["@x/a", "@x/b"]\n\n[github-release]\n')
    got = {d.target.name: d.packages for d in release.read_release(root)}
    assert got == {"npm": ("@x/a", "@x/b"), "github-release": ()}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[pypi]\n", "needs packages"),
        ("[pypi]\npackages = []\n", "needs packages"),
        ('[github-release]\npackages = ["x"]\n', "drop `packages`"),
        ('[pypi]\npackages = ["x"]\nenvironment = "release"\n', "unknown keys"),
        ('[anaconda]\npackages = ["x"]\n', "not a publishing target"),
        ("pypi = 1\n", "must be a table"),
        ("[pypi\n", "release.toml"),
    ],
)
def test_a_malformed_release_toml_is_refused(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        release.read_release(write(tmp_path, text))
