#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Run one MolCrafts CI profile.

The repository selects the profile by name (`CI_PROFILE` in
`.github/partners.env`). The profile file lives in this repository
(`profiles/<name>.yml`). A checkout of molcrafts-ci uses the files beside
this script. A copy downloaded on its own clones `master` and reads that,
so consumers never pin a commit SHA.

  uv run --script hooks/ci.py --stage pre-commit
  uv run --script hooks/ci.py --profile node-python --area lint --list
  uv run --script hooks/ci.py --profile node-python --describe biome
  uv run --script hooks/ci.py --profile node-python --gate biome
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

MASTER = "https://github.com/MolCrafts/molcrafts-ci.git"
OS_USE = re.compile(r"\bstd::os::(?:unix|windows)\b")


def scrub_git_env() -> None:
    """pre-commit exports GIT_DIR for the repository being committed."""
    listed = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        check=False,
        capture_output=True,
        text=True,
    )
    for key in listed.stdout.split():
        os.environ.pop(key, None)


def ci_root() -> Path:
    """Directory that contains profiles/ and actions/check-workflows/."""
    scrub_git_env()
    here = Path(__file__).resolve().parent
    local = here.parent
    if (local / "profiles").is_dir() and (local / "actions" / "check-workflows").is_dir():
        return local
    dest = Path(tempfile.gettempdir()) / f"molcrafts-ci-master-{os.getpid()}"
    if not (dest / ".git").is_dir():
        if dest.exists():
            subprocess.run(["rm", "-rf", str(dest)], check=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "master", MASTER, str(dest)],
            check=True,
        )
    else:
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", "master"], check=True
        )
        subprocess.run(["git", "-C", str(dest), "checkout", "--detach", "FETCH_HEAD"], check=True)
    return dest


def profile_name(cwd: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("CI_PROFILE", "").strip()
    if env:
        return env
    path = cwd / ".github" / "partners.env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CI_PROFILE="):
                return line.split("=", 1)[1].strip()
    sys.exit("CI_PROFILE is not set (.github/partners.env or --profile)")


def load_profile(name: str) -> dict:
    path = ci_root() / "profiles" / f"{name}.yml"
    if not path.is_file():
        known = sorted(p.stem for p in (ci_root() / "profiles").glob("*.yml"))
        sys.exit(f"unknown CI profile {name!r}; choose one of: {', '.join(known)}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("gates"), list):
        sys.exit(f"{path} has no gates")
    return data


def selected(
    profile: dict, stage: str | None, workflow: str | None, gate: str | None
) -> list[dict]:
    gates = []
    for item in profile["gates"]:
        if gate and item.get("id") != gate:
            continue
        if stage and item.get("stage") != stage:
            continue
        if workflow and item.get("workflow") != workflow:
            continue
        gates.append(item)
    if gate and not gates:
        sys.exit(f"profile {profile.get('name')} has no gate {gate!r}")
    return gates


def run_workflows(cwd: Path) -> int:
    script = ci_root() / "actions" / "check-workflows" / "check_workflows.py"
    return subprocess.call([sys.executable, str(script), str(cwd)], cwd=cwd)


def run_os_cfg(cwd: Path) -> int:
    bad: list[str] = []
    skip = {".git", "target", "node_modules", "dist"}
    for path in cwd.rglob("*.rs"):
        if skip.intersection(path.parts):
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if not OS_USE.search(line) or line.lstrip().startswith("//"):
                continue
            prev = lines[index - 1] if index else ""
            if "#[cfg" in prev or "#[cfg" in line or "os-gated" in prev or "os-gated" in line:
                continue
            bad.append(f"{path.relative_to(cwd)}:{index + 1}: std::os without #[cfg")
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    return 0


def run_shell(cwd: Path, command: str) -> int:
    return subprocess.call(["bash", "-euo", "pipefail", "-c", command], cwd=cwd)


def run_gate(cwd: Path, gate: dict) -> int:
    command = str(gate.get("run", "")).strip()
    if command == "molci:workflows":
        return run_workflows(cwd)
    if command == "molci:os-cfg":
        return run_os_cfg(cwd)
    if not command:
        sys.exit(f"gate {gate.get('id')} has no run")
    print(f"== {gate.get('id')} ==")
    return run_shell(cwd, command)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=None)
    parser.add_argument("--stage", choices=("pre-commit", "pre-push"))
    parser.add_argument("--workflow")
    parser.add_argument("--gate")
    parser.add_argument("--area")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--describe", metavar="GATE")
    parser.add_argument("--root", default=".")
    # Some uv versions forward the `--` of `uv run --script ci.py -- ...`; drop one.
    if argv[:1] == ["--"]:
        argv = argv[1:]
    args = parser.parse_args(argv)
    cwd = Path(args.root).resolve()
    name = profile_name(cwd, args.profile)
    profile = load_profile(name)
    workflow = args.workflow or args.area
    if args.list:
        ids = [g["id"] for g in selected(profile, None, workflow, None)]
        print(json.dumps(ids))
        return 0
    if args.describe:
        gate = selected(profile, None, None, args.describe)[0]
        print(json.dumps({"id": gate["id"], "setup": gate.get("setup") or [], "run": gate["run"]}))
        return 0
    if args.gate:
        code = run_gate(cwd, selected(profile, None, None, args.gate)[0])
        return code
    if not args.stage:
        sys.exit("pass --stage, --gate, --list, or --describe")
    failed = 0
    for gate in selected(profile, args.stage, None, None):
        code = run_gate(cwd, gate)
        if code != 0:
            failed = code
            break
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
