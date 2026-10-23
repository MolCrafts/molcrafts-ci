from __future__ import annotations

from pathlib import Path

from molcrafts_ci.config import parse
from molcrafts_ci.plan import Event, legs

CONFIG = parse(
    {
        "tools": {"python": "3.12"},
        "partners": {"molrs": "MolCrafts/molrs@dev"},
        "check": {
            "lint": {"run": "ruff check", "stage": "pre-commit"},
            "test": {
                "run": "pytest",
                "os": ["linux", "macos", "windows"],
                "python": ["3.12", "3.14"],
                "junit": "junit.xml",
            },
            "site": {"run": "npm test", "node": "site/.nvmrc"},
            "published": {"run": "pytest --no-sources", "stage": "release"},
        },
        "dashboard": {"project": "molpy", "branch": "dev"},
    },
    Path("ci.toml"),
)
CI = ("pre-commit", "pre-push")


def event(**kw: str) -> Event:
    base = {
        "owner": "MolCrafts",
        "repository": "MolCrafts/molpy",
        "name": "push",
        "ref": "refs/heads/dev",
    }
    return Event(**(base | kw))


def names(rows: list[dict]) -> list[str]:
    return [r["name"] for r in rows]


def test_integration_push_runs_every_leg() -> None:
    rows = legs(CONFIG, event(), stages=CI)
    # Each OS runs the first Python; the second Python runs on linux only.
    assert names(rows) == [
        "lint",
        "test (linux, 3.12)",
        "test (macos, 3.12)",
        "test (windows, 3.12)",
        "test (linux, 3.14)",
        "site",
    ]
    assert rows[2]["runs-on"] == "macos-latest"


def test_feature_push_upstream_runs_the_first_leg_only() -> None:
    rows = legs(CONFIG, event(ref="refs/heads/fix-parser"), stages=CI)
    assert names(rows) == ["lint", "test (linux, 3.12)", "site"]


def test_fork_runs_everything_but_its_pull_request_runs_nothing() -> None:
    fork = {"owner": "Roy-Kid", "repository": "Roy-Kid/molpy"}
    assert len(legs(CONFIG, event(**fork, ref="refs/heads/fix"), stages=CI)) == 6
    pr = event(**fork, name="pull_request", ref="refs/pull/1/merge", pr_head="Roy-Kid/molpy")
    assert legs(CONFIG, pr, stages=CI) == []


def test_pull_request_from_a_fork_into_upstream_runs() -> None:
    pr = event(name="pull_request", ref="refs/pull/1/merge", pr_head="Roy-Kid/molpy")
    assert len(legs(CONFIG, pr, stages=CI)) == 6


def test_dashboard_publishes_from_one_leg_on_its_branch_only() -> None:
    on_dev = legs(CONFIG, event(), stages=CI)
    assert [r["name"] for r in on_dev if r["dashboard"]] == ["test (linux, 3.12)"]
    assert on_dev[1]["dashboard"] == "molpy"
    assert not any(r["dashboard"] for r in legs(CONFIG, event(ref="refs/heads/master"), stages=CI))
    fork = event(owner="Roy-Kid", repository="Roy-Kid/molpy")
    assert not any(r["dashboard"] for r in legs(CONFIG, fork, stages=CI))


def test_release_stage_is_planned_apart_without_partners() -> None:
    rows = legs(CONFIG, event(ref="refs/tags/v1.0.0"), stages=("release",))
    assert names(rows) == ["published"]
    assert rows[0]["partners"] is False
    assert all(r["partners"] for r in legs(CONFIG, event(), stages=CI))


def test_node_version_file_and_lockfile() -> None:
    site = next(r for r in legs(CONFIG, event(), stages=CI) if r["check"] == "site")
    assert site["node-version-file"] == "site/.nvmrc"
    assert site["node-version"] == ""
    assert site["node-lockfile"] == "site/package-lock.json"
