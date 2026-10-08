"""actions/ci-context's rules, run through context.sh against the same table
of synthetic contexts the `test / ci-context` job feeds the action itself.

The table lives once, in .github/workflows/test.yml; this test reads it from
there, so the two layers cannot drift apart.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "actions/ci-context/context.sh"
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8"))
CASES = WORKFLOW["jobs"]["ci-context"]["strategy"]["matrix"]["include"]


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
    assert outputs(tmp_path) == case["expect"]


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
