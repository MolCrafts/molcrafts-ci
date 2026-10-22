"""molci audit / rulesets against a fake GitHub API (no network)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from molcrafts_ci import settings
from molcrafts_ci.settings import CANONICAL_RULESETS, REQUIRED_CHECK

RELEASE = (
    '[pypi]\npackages = ["pkg"]\n\n[vscode-marketplace]\npackages = ["ext"]\n\n[github-release]\n'
)


class FakeGitHub:
    """Just enough of the REST API: environments, secrets, rulesets."""

    def __init__(
        self, envs: dict[str, set[str]], repo_secrets: set[str], rulesets: dict[str, dict]
    ):
        self.envs = envs
        self.repo_secrets = repo_secrets
        self.rulesets = {i: dict(r, id=i) for i, r in enumerate(rulesets.values(), 1)}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, path: str, *, method: str = "GET", body: dict | None = None):
        self.calls.append((method, path))
        tail = path.split("/", 3)[3]
        if method == "GET" and tail == "environments":
            return {"environments": [{"name": n} for n in self.envs]}
        if method == "GET" and tail.startswith("environments/") and tail.endswith("/secrets"):
            return {"secrets": [{"name": s} for s in self.envs[tail.split("/")[1]]]}
        if method == "GET" and tail == "actions/secrets":
            return {"secrets": [{"name": s} for s in self.repo_secrets]}
        if method == "GET" and tail == "rulesets":
            return [{"id": i, "name": r["name"]} for i, r in self.rulesets.items()]
        if method == "GET" and tail.startswith("rulesets/"):
            return self.rulesets[int(tail.split("/")[1])]
        if method == "POST" and tail == "rulesets":
            new = max(self.rulesets, default=0) + 1
            self.rulesets[new] = dict(body, id=new)
            return self.rulesets[new]
        if method == "PUT" and tail.startswith("rulesets/"):
            self.rulesets[int(tail.split("/")[1])] = dict(body, id=int(tail.split("/")[1]))
            return None
        if method == "DELETE" and tail.startswith("rulesets/"):
            del self.rulesets[int(tail.split("/")[1])]
            return None
        raise AssertionError(f"unexpected call {method} {path}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/release.toml").write_text(RELEASE, encoding="utf-8")
    (tmp_path / ".github/partners.env").write_text("SELF=pkg\n", encoding="utf-8")
    return tmp_path


def canonical() -> FakeGitHub:
    return FakeGitHub(
        {"pypi": set(), "vscode-marketplace": {"VSCE_PAT", "OVSX_PAT"}, "copilot": set()},
        {"CODECOV_TOKEN"},
        copy.deepcopy(CANONICAL_RULESETS),
    )


def run(monkeypatch, repo: Path, fake: FakeGitHub):
    monkeypatch.setattr(settings, "gh", fake)
    return settings.audit(repo, settings.repository_of(repo, None))


def test_a_canonical_repository_has_no_findings(monkeypatch, repo) -> None:
    findings, publishers = run(monkeypatch, repo, canonical())
    assert findings == []
    assert publishers == [
        "PyPI (pkg): Publishing -> GitHub: owner MolCrafts, repository pkg, "
        "workflow release.yml, environment pypi"
    ]


def test_every_drift_is_a_finding(monkeypatch, repo) -> None:
    fake = canonical()
    del fake.envs["pypi"]
    fake.envs["vscode-marketplace"] = {"VSCE_PAT"}
    fake.envs["release-core"] = set()
    fake.repo_secrets |= {"VSCE_PAT", "CARGO_REGISTRY_TOKEN"}
    ci = next(r for r in fake.rulesets.values() if r["name"] == "ci")
    ci["rules"][0]["parameters"]["required_status_checks"] = [{"context": "test / context"}]
    fake.rulesets[99] = {"id": 99, "name": "require-green-ci", "rules": []}
    findings, _ = run(monkeypatch, repo, fake)
    assert sorted(str(f) for f in findings) == sorted(
        [
            "[environment] `pypi` is missing; pypi publishes through it",
            "[environment] `vscode-marketplace` lacks the secret OVSX_PAT",
            "[environment] `release-core` serves no declared target; "
            "delete it, or declare its target",
            "[secret] repository secret CARGO_REGISTRY_TOKEN publishes; "
            "no declared target needs it (trusted publishing needs no token); delete it",
            "[secret] repository secret VSCE_PAT publishes; "
            "move it into environment `vscode-marketplace`",
            "[ruleset] `ci` differs from the canonical one (molci rulesets --apply)",
            "[ruleset] `require-green-ci` is not a canonical ruleset "
            "(molci rulesets --apply --prune)",
        ]
    )


def test_apply_writes_the_canonical_rulesets_and_prunes_the_rest(monkeypatch, repo) -> None:
    fake = FakeGitHub(
        {},
        set(),
        {
            "protect-master": {"name": "protect-master", "target": "branch", "rules": []},
            "require-green-ci": {"name": "require-green-ci", "rules": []},
        },
    )
    monkeypatch.setattr(settings, "gh", fake)
    done = settings.apply_rulesets("MolCrafts/pkg", prune=True)
    assert done == ["created ci", "updated protect-master", "deleted require-green-ci"]
    assert (
        settings.audit_rulesets("MolCrafts/pkg", settings.current_rulesets("MolCrafts/pkg")) == []
    )
    assert settings.apply_rulesets("MolCrafts/pkg", prune=True) == []  # idempotent


def test_the_one_required_check_is_what_check_workflows_enforces() -> None:
    import importlib.util
    import sys

    path = Path(__file__).resolve().parent.parent / "actions/check-workflows/check_workflows.py"
    spec = importlib.util.spec_from_file_location("cw_for_settings", path)
    cw = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cw
    spec.loader.exec_module(cw)
    assert cw.RESULT_CHECK == REQUIRED_CHECK
    [rule] = CANONICAL_RULESETS["ci"]["rules"]
    assert rule["parameters"]["required_status_checks"] == [{"context": REQUIRED_CHECK}]
