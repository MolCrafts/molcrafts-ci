from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from molcrafts_ci.config import ConfigError, parse
from molcrafts_ci.run import run_checks, select

CONFIG = parse(
    {
        "env": {"GREETING": "hello"},
        "check": {
            "lint": {"run": "echo lint >> log", "stage": "pre-commit"},
            "test": {
                "run": ['echo "$GREETING $UV_PYTHON" >> log', "false | cat", "echo never >> log"]
            },
            "published": {"run": "echo published >> log", "stage": "release"},
        },
    },
    Path("ci.toml"),
)


def test_select_by_name_stage_or_everything_but_release() -> None:
    assert [c.name for c in select(CONFIG, ["test"], None)] == ["test"]
    assert [c.name for c in select(CONFIG, [], "pre-commit")] == ["lint"]
    assert [c.name for c in select(CONFIG, [], None)] == ["lint", "test"]
    with pytest.raises(ConfigError, match="no \\[check.docs\\]"):
        select(CONFIG, ["docs"], None)


def test_runs_commands_in_order_with_env_and_stops_at_a_failure(tmp_path: Path) -> None:
    logs: list[str] = []
    code = run_checks(tmp_path, CONFIG, select(CONFIG, [], None), python="3.13", log=logs.append)
    assert code == 1  # pipefail: `false | cat` fails
    assert (tmp_path / "log").read_text().splitlines() == ["lint", "hello 3.13"]
    assert logs[-1] == "molci: check `test` failed (exit 1): false | cat"


def test_missing_partner_is_named(tmp_path: Path) -> None:
    config = parse(
        {"partners": {"nope": "MolCrafts/nope@dev"}, "check": {"t": {"run": "true"}}},
        Path("ci.toml"),
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(RuntimeError, match=r"missing partner checkout \.\./nope"):
        run_checks(repo, config, list(config.checks), log=lambda _: None)


def test_existing_partner_reports_its_branch(tmp_path: Path) -> None:
    sibling = tmp_path / "molrs"
    subprocess.run(["git", "init", "-q", "-b", "dev", str(sibling)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(sibling),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        check=True,
    )
    config = parse(
        {"partners": {"molrs": "MolCrafts/molrs@dev"}, "check": {"t": {"run": "true"}}},
        Path("ci.toml"),
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    logs: list[str] = []
    assert run_checks(repo, config, list(config.checks), log=logs.append) == 0
    assert logs[0].startswith("molrs: ../molrs is dev @ ")
    assert logs[0].endswith("(CI uses dev)")
