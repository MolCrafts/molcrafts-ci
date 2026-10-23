from __future__ import annotations

import re
from pathlib import Path

import pytest

from molcrafts_ci.config import ConfigError, load

MOLPY = """
[env]
PYTHONWARNDEFAULTENCODING = "1"

[tools]
python = "3.12"
rust = true

[partners]
molrs = "MolCrafts/molrs@dev"

[check.lint]
stage = "pre-commit"
run = ["uvx ruff check src", "uvx ty check src"]

[check.test]
run = "uv run pytest"
os = ["linux", "macos", "windows"]
python = ["3.12", "3.14"]
junit = ".ci-out/junit.xml"
coverage = ".ci-out/coverage.json"

[dashboard]
project = "molpy"
branch = "dev"
"""


def write(tmp_path: Path, text: str) -> Path:
    (tmp_path / ".github").mkdir(exist_ok=True)
    (tmp_path / ".github/ci.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_reads_every_table(tmp_path: Path) -> None:
    config = load(write(tmp_path, MOLPY))
    assert config.env == {"PYTHONWARNDEFAULTENCODING": "1"}
    assert [(p.name, p.repository, p.ref) for p in config.partners] == [
        ("molrs", "MolCrafts/molrs", "dev")
    ]
    lint, test = config.checks
    assert lint.run == ("uvx ruff check src", "uvx ty check src")
    assert lint.stage == "pre-commit"
    assert lint.os == ("linux",)
    # [tools] fills in what a check does not say.
    assert lint.python == ("3.12",) and lint.rust is True
    assert test.python == ("3.12", "3.14")
    assert config.dashboard.project == "molpy" and config.dashboard.branch == "dev"


def test_partners_are_optional(tmp_path: Path) -> None:
    config = load(write(tmp_path, '[check.test]\nrun = "pytest"\n'))
    assert config.partners == ()
    assert config.checks[0].stage == "pre-push"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('[check.test]\nrun = "x"\nstgae = "pre-push"\n', "check.test.stgae: unknown key"),
        ("[check.test]\nrun = []\n", "check.test.run: must be a command"),
        ('[check.test]\nrun = "x"\nos = ["ubuntu"]\n', "check.test.os: must list"),
        ('[check.test]\nrun = "x"\nstage = "push"\n', "check.test.stage: must be one of"),
        ('[partners]\nmolrs = "molrs"\n[check.t]\nrun = "x"\n', "partners.molrs: must read"),
        ('[partners]\nmolrs = "MolCrafts/molrs@0123abc"\n', "ci.toml: no [check.<name>]"),
        (
            '[check.t]\nrun = "x"\n[dashboard]\nproject = "p"\n',
            "dashboard: needs a check with `junit`",
        ),
        ('[check.Test]\nrun = "x"\n', "check.Test: a check name is lower case"),
    ],
)
def test_mistakes_name_the_key(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=re.escape(message)):
        load(write(tmp_path, text))


def test_missing_file_says_what_it_is_for(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="lists what this repository checks"):
        load(tmp_path)
