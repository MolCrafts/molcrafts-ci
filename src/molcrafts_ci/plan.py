"""Which jobs a CI run starts, from `.github/ci.toml` and where the run happens.

The rules, in full:

- A pull request inside a fork is skipped: the push to that fork already ran
  every check.
- A push to a feature branch of MolCrafts runs the first leg of each check
  (linux, the first Python). Every other run (dev, master, tags, pull
  requests, forks, dispatches) runs every leg.
- Each OS runs the first Python of a check; any further Python runs on the
  first OS only.
- A push to the `[dashboard]` branch on MolCrafts publishes what each check
  with a `dashboard` record measured, from its first leg.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from molcrafts_ci.config import OSES, Check, Config

UPSTREAM_OWNER = "MolCrafts"
INTEGRATION_BRANCHES = ("refs/heads/dev", "refs/heads/master", "refs/heads/main")


@dataclass(frozen=True)
class Event:
    """The facts about a run that decide its jobs (GitHub's `github` context)."""

    owner: str
    repository: str
    name: str
    ref: str
    pr_head: str = ""

    @property
    def upstream(self) -> bool:
        return self.owner == UPSTREAM_OWNER

    @property
    def fork_pull_request(self) -> bool:
        return self.name == "pull_request" and self.pr_head == self.repository and not self.upstream

    @property
    def feature_push(self) -> bool:
        integration = self.ref in INTEGRATION_BRANCHES or self.ref.startswith("refs/tags/")
        return self.upstream and self.name == "push" and not integration


def legs(config: Config, event: Event, *, stages: tuple[str, ...]) -> list[dict[str, Any]]:
    """The matrix rows for the `check` job: one per check, OS and Python."""
    if event.fork_pull_request:
        return []
    rows: list[dict[str, Any]] = []
    publishing = _publishing(config, event)
    for check in config.checks:
        if check.stage not in stages:
            continue
        expanded = _expand(check)
        if event.feature_push:
            expanded = expanded[:1]
        for i, (os_name, python) in enumerate(expanded):
            rows.append(_row(config, check, os_name, python, dashboard=publishing and i == 0))
    return rows


def _expand(check: Check) -> list[tuple[str, str]]:
    pythons = check.python or ("",)
    first, *rest = pythons
    return [(os_name, first) for os_name in check.os] + [(check.os[0], p) for p in rest]


def _publishing(config: Config, event: Event) -> bool:
    dashboard = config.dashboard
    return (
        dashboard is not None
        and event.upstream
        and event.name == "push"
        and event.ref == f"refs/heads/{dashboard.branch}"
    )


def _row(config: Config, check: Check, os_name: str, python: str, *, dashboard: bool) -> dict:
    label = []
    if len(check.os) > 1:
        label.append(os_name)
    if len(check.python) > 1:
        label.append(python)
    node_file = check.node if check.node and check.node.endswith(".nvmrc") else ""
    lockfile = (
        Path(node_file).parent / "package-lock.json" if node_file else Path("package-lock.json")
    )
    return {
        "name": f"{check.name} ({', '.join(label)})" if label else check.name,
        "check": check.name,
        "runs-on": OSES[os_name],
        "python": python,
        "node-version": "" if node_file else (check.node or ""),
        "node-version-file": node_file,
        "node-lockfile": lockfile.as_posix() if check.node else "",
        "rust": check.rust,
        "partners": bool(config.partners) and check.stage != "release",
        "junit": check.junit or "",
        "cargo-test": check.cargo_test or "",
        "coverage": check.coverage or "",
        "dashboard": config.dashboard.project if dashboard and check.dashboard else "",
        "record": check.dashboard or "",
    }
