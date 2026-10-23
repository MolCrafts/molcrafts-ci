"""Run the checks `.github/ci.toml` lists: the same commands in git hooks and CI.

Each command runs from the repository root the way a GitHub `shell: bash`
step does (`bash --noprofile --norc -eo pipefail`), so a multi-line command
stops at its first error and a pipe fails when any part of it does. `[env]` is
added to the environment. A heavy (pre-push) check is handed to
`$MOLCRAFTS_HOOK_RUNNER` when that is set and this is not already a Slurm job,
so a cluster can run it on a compute node.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

from molcrafts_ci import workspace
from molcrafts_ci.config import STAGES, Check, Config, ConfigError


def select(config: Config, names: Iterable[str], stage: str | None) -> list[Check]:
    """The checks to run: the named ones, or every one of a stage, in file order."""
    names = list(names)
    if names and stage:
        raise ConfigError("name checks or pass --stage, not both")
    if names:
        return [config.check(name) for name in names]
    if stage:
        if stage not in STAGES:
            raise ConfigError(f"--stage must be one of {', '.join(STAGES)}")
        return [c for c in config.checks if c.stage == stage]
    return [c for c in config.checks if c.stage != "release"]


def run_checks(
    root: Path,
    config: Config,
    checks: list[Check],
    *,
    python: str | None = None,
    log: Callable[[str], None] = workspace.stderr,
) -> int:
    """Run each check's commands in order; stop at the first that fails."""
    if not checks:
        log("molci: no checks to run")
        return 0
    if config.partners and any(c.stage != "release" for c in checks):
        workspace.require(root, config, log=log)
    env = workspace.clean_git_env() | config.env
    # Checks run in the repository's own environment, not in the one molci
    # happens to be installed in (uvx, a hook's tool venv).
    env.pop("VIRTUAL_ENV", None)
    if python:
        env["UV_PYTHON"] = python
    bash = shutil.which("bash") or "bash"
    for check in checks:
        log(f"== {check.name}")
        for command in check.run:
            log(f"$ {command}")
            argv = _wrap(check, [bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", command])
            code = subprocess.run(argv, cwd=root, env=env, check=False).returncode
            if code:
                log(f"molci: check `{check.name}` failed (exit {code}): {command}")
                return code
    return 0


def _wrap(check: Check, argv: list[str]) -> list[str]:
    runner = os.environ.get("MOLCRAFTS_HOOK_RUNNER")
    if check.stage == "pre-push" and runner and not os.environ.get("SLURM_JOB_ID"):
        return [runner, *argv]
    return argv
