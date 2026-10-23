"""Context scenarios run locally and in the Python gate; one hosted job checks wiring."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "actions/ci-context/context.sh"
CASES = yaml.safe_load((ROOT / "tests/fixtures/ci-context.yml").read_text(encoding="utf-8"))


def run(tmp_path: Path, **ctx: str) -> subprocess.CompletedProcess[str]:
    out = tmp_path / "out"
    out.touch()
    env = {k: v for k, v in os.environ.items() if not k.startswith("CI_")}
    env.update({f"CI_{k.upper()}": v for k, v in ctx.items()}, GITHUB_OUTPUT=str(out))
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)


def outputs(tmp_path: Path) -> dict[str, str]:
    text = (tmp_path / "out").read_text(encoding="utf-8")
    return dict(line.split("=", 1) for line in text.splitlines())


def test_table_covers_every_kind_of_run() -> None:
    events = {c["event"] for c in CASES}
    assert {"push", "pull_request", "workflow_dispatch", "schedule"} <= events
    assert any(c["ref"].startswith("refs/tags/") for c in CASES)
    assert any(c["expect"]["skip-pr"] == "true" for c in CASES)
    assert any(c["expect"]["tier"] == "fast" for c in CASES)
    # publish: the upstream v* tag push, and the near misses around it.
    assert [c["case"] for c in CASES if c["expect"]["publish"] == "true"] == ["upstream tag"]
    names = {c["case"] for c in CASES}
    assert {"fork tag", "upstream master push", "upstream dispatch on a tag"} <= names


@pytest.mark.parametrize(
    ("owner", "event", "ref", "publish"),
    [
        ("MolCrafts", "push", "refs/tags/v0.16.0", "true"),
        ("MolCrafts", "push", "refs/tags/v1", "true"),
        ("Roy-Kid", "push", "refs/tags/v0.16.0", "false"),  # a fork's tag
        ("MolCrafts", "push", "refs/heads/master", "false"),  # a branch, even master
        ("MolCrafts", "push", "refs/heads/v0.16.0", "false"),  # a branch named like a tag
        ("MolCrafts", "push", "refs/tags/release-0.16", "false"),  # not a v* tag
        ("MolCrafts", "workflow_dispatch", "refs/tags/v0.16.0", "false"),  # the dry run
        ("MolCrafts", "schedule", "refs/tags/v0.16.0", "false"),
    ],
)
def test_publish(tmp_path: Path, owner: str, event: str, ref: str, publish: str) -> None:
    proc = run(tmp_path, owner=owner, repository=f"{owner}/molrs", event=event, ref=ref)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert outputs(tmp_path)["publish"] == publish


def test_outputs_are_the_action_outputs(tmp_path: Path) -> None:
    action = yaml.safe_load((ROOT / "actions/ci-context/action.yml").read_text(encoding="utf-8"))
    run(
        tmp_path,
        owner="MolCrafts",
        repository="MolCrafts/molrs",
        event="push",
        ref="refs/heads/dev",
    )
    assert list(outputs(tmp_path)) == list(action["outputs"])
    assert "cancel" not in action["outputs"]


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_case(tmp_path: Path, case: dict) -> None:
    proc = run(
        tmp_path,
        owner=case["owner"],
        repository=case["repository"],
        event=case["event"],
        ref=case["ref"],
        pr_head=case["head"],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert outputs(tmp_path) == {
        **case["expect"],
        "nightly": "false",
        "source-ref": case["ref"],
        "deploy": "true" if case["case"] == "upstream master push" else "false",
    }


@pytest.mark.parametrize(
    ("owner", "event", "ref", "workflow", "enabled"),
    [
        ("MolCrafts", "schedule", "refs/heads/master", "nightly", True),
        ("MolCrafts", "workflow_dispatch", "refs/heads/dev", "nightly", True),
        ("MolCrafts", "workflow_dispatch", "refs/heads/master", "nightly", True),
        ("Roy-Kid", "schedule", "refs/heads/master", "nightly", False),
        ("MolCrafts", "push", "refs/heads/nightly", "nightly", False),
        ("MolCrafts", "workflow_dispatch", "refs/heads/feature", "nightly", False),
        ("MolCrafts", "workflow_dispatch", "refs/tags/v1.0.0", "nightly", False),
        ("MolCrafts", "schedule", "refs/heads/master", "test", False),
    ],
)
def test_nightly_selects_dev_only_for_the_nightly_channel(
    tmp_path: Path, owner: str, event: str, ref: str, workflow: str, enabled: bool
) -> None:
    proc = run(
        tmp_path, owner=owner, repository=f"{owner}/molrs", event=event, ref=ref, workflow=workflow
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    got = outputs(tmp_path)
    assert got["nightly"] == str(enabled).lower()
    assert got["source-ref"] == ("refs/heads/dev" if enabled else ref)
    assert got["publish"] == "false"


@pytest.mark.parametrize(
    ("owner", "event", "ref", "enabled"),
    [
        ("MolCrafts", "push", "refs/heads/master", True),
        ("MolCrafts", "workflow_dispatch", "refs/heads/master", True),
        ("MolCrafts", "repository_dispatch", "refs/heads/master", True),
        ("MolCrafts", "push", "refs/heads/dev", False),
        ("MolCrafts", "workflow_dispatch", "refs/heads/dev", False),
        ("MolCrafts", "push", "refs/tags/v1.0.0", False),
        ("Roy-Kid", "push", "refs/heads/master", False),
    ],
)
def test_deploy_is_a_stable_upstream_branch_operation(
    tmp_path: Path, owner: str, event: str, ref: str, enabled: bool
) -> None:
    proc = run(tmp_path, owner=owner, repository=f"{owner}/molrs", event=event, ref=ref)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert outputs(tmp_path)["deploy"] == str(enabled).lower()


@pytest.mark.parametrize("missing", ["owner", "repository", "event", "ref"])
def test_missing_context_fails(tmp_path: Path, missing: str) -> None:
    ctx = dict(owner="MolCrafts", repository="MolCrafts/molrs", event="push", ref="refs/heads/dev")
    ctx[missing] = ""
    proc = run(tmp_path, **ctx)
    assert proc.returncode != 0
    assert f"CI_{missing.upper()} is empty" in proc.stdout
    assert (tmp_path / "out").read_text(encoding="utf-8") == ""


def test_pull_request_from_a_deleted_fork_runs(tmp_path: Path) -> None:
    proc = run(
        tmp_path,
        owner="Roy-Kid",
        repository="Roy-Kid/molrs",
        event="pull_request",
        ref="refs/pull/9/merge",
        pr_head="",
    )
    assert proc.returncode == 0
    assert outputs(tmp_path)["skip-pr"] == "false"
