#!/usr/bin/env python3
"""Local/CI gates. Run through uv run --locked --extra dev scripts/check.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
NPM = shutil.which("npm") or "npm"
GATES = {
    "dependencies": [["uv", "lock", "--check"], ["uv", "pip", "check"]],
    "lint": [
        [PYTHON, "-m", "ruff", "check", "src", "tests", "scripts", "actions"],
        [PYTHON, "-m", "ruff", "format", "--check", "src", "tests", "scripts", "actions"],
        [PYTHON, "scripts/check_repo.py"],
        [PYTHON, "actions/check-workflows/check_workflows.py"],
    ],
    "actions": [
        [
            PYTHON,
            "-m",
            "check_jsonschema",
            "--builtin-schema",
            "vendor.github-actions",
            *map(str, sorted((ROOT / "actions").glob("*/action.yml"))),
        ],
        [
            PYTHON,
            "-m",
            "check_jsonschema",
            "--builtin-schema",
            "vendor.github-workflows",
            *map(str, sorted((ROOT / ".github/workflows").glob("*.yml"))),
        ],
        ["actionlint", "-color"],
    ],
    "python": [[PYTHON, "-m", "pytest", "-q"]],
    "site-types": [[NPM, "--prefix", "site", "run", "typecheck"]],
    "site-test": [[NPM, "--prefix", "site", "test"]],
    "site-build": [[NPM, "--prefix", "site", "run", "build"]],
}


def main() -> int:
    gates = sys.argv[1:]
    if gates == ["all"]:
        gates = list(GATES)
    if not gates or any(gate not in GATES for gate in gates):
        print(f"usage: check.py all | {' '.join(GATES)}", file=sys.stderr)
        return 2
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    for gate in gates:
        if gate == "dependencies":
            exported = subprocess.check_output(
                [
                    "uv",
                    "export",
                    "--locked",
                    "--no-dev",
                    "--no-hashes",
                    "--no-emit-project",
                    "--no-header",
                    "--no-annotate",
                ],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
            )
            if exported != (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8"):
                print(
                    "requirements-runtime.txt differs from uv.lock; regenerate it", file=sys.stderr
                )
                return 1
        if gate.startswith("site-"):
            wanted = (ROOT / "site/.nvmrc").read_text(encoding="utf-8").strip()
            actual = subprocess.check_output(["node", "--version"], text=True).strip().lstrip("v")
            if not (actual == wanted or actual.startswith(wanted + ".")):
                print(f"Node {wanted} is required by site/.nvmrc; found {actual}", file=sys.stderr)
                return 1
        if gate == "actions":
            from bootstrap import actionlint

            GATES["actions"][-1][0] = str(actionlint())
        print(f"== {gate}", flush=True)
        for command in GATES[gate]:
            if shutil.which(command[0]) is None:
                print(f"Required tool missing: {command[0]}", file=sys.stderr)
                return 1
            result = subprocess.run(command, cwd=ROOT, env=env, check=False)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
