"""A repository's GitHub settings, held to the CI scheme and its release.toml.

``molci audit`` reads a repository's environments, their secrets, its
repository-level secrets and its branch rulesets through the GitHub API and
reports every difference from what the scheme and ``.github/release.toml``
imply. ``molci rulesets`` writes the canonical rulesets.

Two rulesets protect every repository, and nothing else:

* ``ci`` on ``dev`` and the default branch: the one required check
  ``test / result``, which test.yml's last job reports (check-workflows
  enforces that job), so renaming or adding a job never strands a pull request;
* ``protect-master`` on the default branch: no deletion, no force push, changes
  through a pull request.

The registries' own trusted-publisher settings are not visible through the
GitHub API; the audit prints what each must say.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from molcrafts_ci import release

REQUIRED_CHECK = "test / result"

CANONICAL_RULESETS: dict[str, dict] = {
    "ci": {
        "name": "ci",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {"include": ["refs/heads/dev", "~DEFAULT_BRANCH"], "exclude": []}
        },
        "bypass_actors": [],
        "rules": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "do_not_enforce_on_create": True,
                    "required_status_checks": [{"context": REQUIRED_CHECK}],
                    "strict_required_status_checks_policy": False,
                },
            }
        ],
    },
    "protect-master": {
        "name": "protect-master",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [],
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "allowed_merge_methods": ["merge", "squash", "rebase"],
                    "dismiss_stale_reviews_on_push": False,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_approving_review_count": 0,
                    "required_review_thread_resolution": False,
                },
            },
        ],
    },
}

_TRUSTED = {
    "pypi": "PyPI ({package}): Publishing -> GitHub: owner {owner}, repository {repo}, "
    "workflow {workflow}, environment {environment}",
    "npm": "npm ({package}): Settings -> Trusted Publisher -> GitHub Actions: "
    "{owner}/{repo}, workflow {workflow}, environment {environment}",
    "crates-io": "crates.io ({package}): Settings -> Trusted Publishing -> GitHub: "
    "{owner}/{repo}, workflow {workflow}, environment {environment}",
}


class GitHubError(RuntimeError):
    """A GitHub API call failed."""


def gh(path: str, *, method: str = "GET", body: dict | None = None) -> object:
    """One GitHub REST call through the `gh` CLI (its token, its host)."""
    cmd = ["gh", "api", "--method", method, path]
    if body is not None:
        cmd += ["--input", "-"]
    proc = subprocess.run(
        cmd,
        input=None if body is None else json.dumps(body),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        raise GitHubError(f"gh api {method} {path}: {proc.stderr.strip() or proc.stdout.strip()}")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


@dataclass(frozen=True)
class Finding:
    area: str  # environment | secret | ruleset | release
    message: str

    def __str__(self) -> str:
        return f"[{self.area}] {self.message}"


def repository_of(root: Path, explicit: str | None) -> str:
    """``OWNER/NAME``: given, or MolCrafts/<SELF> from .github/partners.env."""
    if explicit:
        return explicit
    path = root / ".github" / "partners.env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("SELF="):
                return f"MolCrafts/{line.split('=', 1)[1].strip()}"
    raise ValueError("no --repo, and .github/partners.env names no SELF")


def _ruleset_shape(ruleset: dict) -> dict:
    """The fields the canonical rulesets fix, in comparable form."""
    rules = []
    for rule in ruleset.get("rules", []):
        params = dict(rule.get("parameters") or {})
        if rule["type"] == "required_status_checks":
            params["required_status_checks"] = sorted(
                c["context"] for c in params.get("required_status_checks", [])
            )
        if rule["type"] == "pull_request":
            want = CANONICAL_RULESETS["protect-master"]["rules"][2]["parameters"]
            params = {k: params.get(k) for k in want}
            params["allowed_merge_methods"] = sorted(params.get("allowed_merge_methods") or [])
        rules.append({"type": rule["type"], "parameters": params or None})
    ref = (ruleset.get("conditions") or {}).get("ref_name") or {}
    return {
        "target": ruleset.get("target"),
        "enforcement": ruleset.get("enforcement"),
        "include": sorted(ref.get("include") or []),
        "rules": sorted(rules, key=lambda r: r["type"]),
    }


def current_rulesets(repo: str) -> dict[str, dict]:
    out = {}
    for item in gh(f"repos/{repo}/rulesets") or []:
        out[item["name"]] = gh(f"repos/{repo}/rulesets/{item['id']}")
    return out


def audit_rulesets(repo: str, rulesets: dict[str, dict]) -> list[Finding]:
    found = []
    for name, want in CANONICAL_RULESETS.items():
        if name not in rulesets:
            found.append(Finding("ruleset", f"`{name}` is missing (molci rulesets --apply)"))
        elif _ruleset_shape(rulesets[name]) != _ruleset_shape(want):
            found.append(
                Finding(
                    "ruleset", f"`{name}` differs from the canonical one (molci rulesets --apply)"
                )
            )
    for name in sorted(set(rulesets) - set(CANONICAL_RULESETS)):
        found.append(
            Finding(
                "ruleset", f"`{name}` is not a canonical ruleset (molci rulesets --apply --prune)"
            )
        )
    return found


def audit_environments(repo: str, declared: list[release.Declared]) -> list[Finding]:
    found = []
    envs = {
        e["name"]: {
            s["name"]
            for s in (gh(f"repos/{repo}/environments/{e['name']}/secrets") or {}).get("secrets", [])
        }
        for e in (gh(f"repos/{repo}/environments") or {}).get("environments", [])
    }
    wanted = {d.target.environment: d.target for d in declared if d.target.environment}
    for env, tgt in sorted(wanted.items()):
        if env not in envs:
            found.append(
                Finding("environment", f"`{env}` is missing; {tgt.name} publishes through it")
            )
            continue
        for secret in tgt.secrets:
            if secret not in envs[env]:
                found.append(Finding("environment", f"`{env}` lacks the secret {secret}"))
    for env in sorted(set(envs) - set(wanted) - release.PLATFORM_ENVIRONMENTS):
        found.append(
            Finding(
                "environment",
                f"`{env}` serves no declared target; delete it, or declare its target",
            )
        )
    repo_secrets = {
        s["name"] for s in (gh(f"repos/{repo}/actions/secrets") or {}).get("secrets", [])
    }
    for secret in sorted(repo_secrets & release.PUBLISH_SECRETS):
        homes = sorted(env for env, tgt in wanted.items() if secret in tgt.secrets)
        if homes:
            fix = f"move it into environment `{homes[0]}`"
        else:
            fix = "no declared target needs it (trusted publishing needs no token); delete it"
        found.append(Finding("secret", f"repository secret {secret} publishes; {fix}"))
    return found


def trusted_publishers(repo: str, declared: list[release.Declared]) -> list[str]:
    owner, name = repo.split("/", 1)
    lines = []
    for d in declared:
        template = _TRUSTED.get((d.target.trusted or "").removesuffix(release.NIGHTLY))
        for package in d.packages if template else ():
            lines.append(
                template.format(
                    package=package,
                    owner=owner,
                    repo=name,
                    workflow=d.target.workflow_file,
                    environment=d.target.environment,
                )
            )
    return lines


def audit(root: Path, repo: str) -> tuple[list[Finding], list[str]]:
    """Every finding for ``repo`` (checked out at ``root``) and the trusted
    publishers its registries must name."""
    try:
        declared = release.read_release(root)
    except ValueError as exc:
        return [Finding("release", str(exc))], []
    declared = declared or []
    findings = audit_environments(repo, declared) + audit_rulesets(repo, current_rulesets(repo))
    return findings, trusted_publishers(repo, declared)


def apply_rulesets(repo: str, *, prune: bool) -> list[str]:
    """Create or replace the canonical rulesets; with ``prune``, delete the rest."""
    done = []
    current = current_rulesets(repo)
    for name, want in CANONICAL_RULESETS.items():
        if name in current and _ruleset_shape(current[name]) == _ruleset_shape(want):
            continue
        if name in current:
            gh(f"repos/{repo}/rulesets/{current[name]['id']}", method="PUT", body=want)
            done.append(f"updated {name}")
        else:
            gh(f"repos/{repo}/rulesets", method="POST", body=want)
            done.append(f"created {name}")
    for name in sorted(set(current) - set(CANONICAL_RULESETS)) if prune else []:
        gh(f"repos/{repo}/rulesets/{current[name]['id']}", method="DELETE")
        done.append(f"deleted {name}")
    return done
