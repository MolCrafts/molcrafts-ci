"""Gate lifecycle decisions do not rely on hook callers' claims."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "actions/ci-context/context.sh"


@pytest.mark.parametrize(
    "repo,event,ref,head,intent,validate,native,publish",
    [
        ("Roy-Kid/molpy", "push", "refs/heads/dev", "", "fork-development", False, False, False),
        (
            "MolCrafts/molpy",
            "pull_request",
            "refs/pull/1/merge",
            "Roy-Kid/molpy",
            "pull-request",
            True,
            True,
            False,
        ),
        (
            "MolCrafts/molpy",
            "push",
            "refs/heads/feature",
            "",
            "fork-development",
            False,
            False,
            False,
        ),
        ("MolCrafts/molpy", "push", "refs/heads/dev", "", "integration", True, False, False),
        ("MolCrafts/molpy", "push", "refs/heads/master", "", "integration", True, True, False),
        (
            "MolCrafts/molpy",
            "pull_request",
            "refs/pull/2/merge",
            "MolCrafts/molpy",
            "pull-request",
            True,
            True,
            False,
        ),
        (
            "MolCrafts/molpy",
            "pull_request",
            "refs/pull/3/merge",
            "external/molpy",
            "pull-request",
            True,
            True,
            False,
        ),
        ("MolCrafts/molpy", "push", "refs/tags/v1.0.0", "", "release", True, False, True),
        (
            "MolCrafts/molpy",
            "workflow_dispatch",
            "refs/heads/dev",
            "",
            "integration",
            True,
            True,
            False,
        ),
        ("MolCrafts/molpy", "schedule", "refs/heads/master", "", "nightly", True, True, False),
        ("Roy-Kid/molpy", "push", "refs/tags/v1.0.0", "", "fork-development", False, False, False),
        (
            "MolCrafts/other",
            "push",
            "refs/tags/v1.0.0",
            "",
            "fork-development",
            False,
            False,
            False,
        ),
    ],
)
def test_lifecycle(repo, event, ref, head, intent, validate, native, publish):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CI_") and k != "GITHUB_OUTPUT"}
    env.update(
        CI_PROFILE="rust-python",
        CI_OWNER=repo.split("/")[0],
        CI_REPOSITORY=repo,
        CI_EVENT=event,
        CI_REF=ref,
        CI_PR_HEAD=head,
        CI_WORKFLOW="nightly" if event == "schedule" else "test",
    )
    run = subprocess.run(["bash", str(SCRIPT)], env=env, check=True, capture_output=True, text=True)
    out = dict(line.split("=", 1) for line in run.stdout.splitlines())
    assert out["intent"] == intent
    assert out["validate"] == str(validate).lower()
    assert out["native"] == str(native).lower()
    assert out["publish"] == str(publish).lower()
    assert out["skip-pr"] == "false"
