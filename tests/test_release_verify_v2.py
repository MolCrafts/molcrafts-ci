"""A green check on an unrelated/PR/fork commit is never release evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_verify", Path(__file__).parents[1] / "actions/release-verify/verify.py"
)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def good():
    return dict(
        id=1,
        head_sha="a" * 40,
        head_branch="master",
        event="push",
        path=".github/workflows/test.yml",
        repository={"full_name": "MolCrafts/molpy"},
        head_repository={"full_name": "MolCrafts/molpy"},
        status="completed",
        conclusion="success",
        run_attempt=1,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("head_sha", "b" * 40),
        ("head_branch", "dev"),
        ("event", "pull_request"),
        ("path", ".github/workflows/other.yml"),
        ("repository", {"full_name": "Roy-Kid/molpy"}),
        ("head_repository", {"full_name": "Roy-Kid/molpy"}),
    ],
)
def test_exact_trusted_run_identity(field, value):
    run = good()
    assert VERIFY.eligible(run, "MolCrafts/molpy", "a" * 40)
    run[field] = value
    assert not VERIFY.eligible(run, "MolCrafts/molpy", "a" * 40)


@pytest.mark.parametrize("status", ["skipped", "failure", "cancelled", None])
def test_required_native_cannot_be_skipped(monkeypatch, status):
    monkeypatch.setenv("PUBLISH", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "MolCrafts/molpy")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    jobs = [
        {"name": "test / result", "conclusion": "success"},
        {"name": "test / native", "conclusion": status},
    ]
    jobs += [
        {"name": f"test / platform ({p})", "conclusion": "success"}
        for p in ("windows", "macos", "wasm")
    ]
    monkeypatch.setattr(
        VERIFY,
        "api",
        lambda path: [{"jobs": jobs}] if "/jobs?" in path else [{"workflow_runs": [good()]}],
    )
    with pytest.raises(ValueError, match="requires successful"):
        VERIFY.main()


def test_manual_dry_run_never_requests_release_attestation(monkeypatch):
    monkeypatch.setenv("PUBLISH", "false")
    monkeypatch.setattr(VERIFY, "api", lambda path: pytest.fail("dry run queried release evidence"))
    assert VERIFY.main() == 0
