#!/usr/bin/env python3
"""
Repository invariants that no formatter or type checker can see.

Each check here exists because the thing it looks for actually shipped and
broke something. They are cheap, they run in pre-commit and in CI, and they
are deliberately narrow: a check that guesses produces noise, and noise is
how a gate stops being read.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def default_branch() -> str | None:
    """The branch a push-triggered workflow has to name to ever run.

    Read from the remote rather than from HEAD: the check is about where the
    repository publishes from, not about where the author happens to be
    standing. Comparing against the current branch made every feature branch
    fail this check.
    """
    head = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.split("/", 1)[1] if "/" in head else head
    # No remote (a fresh clone-less tree, or a fork without origin/HEAD): fall
    # back to where we are, which is the best guess available.
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    return None if branch in (None, "HEAD") else branch


def check_workflow_branches() -> list[str]:
    """
    A push-triggered workflow must list the branch it is meant to run on.

    `publish.yml` listened only to `main` after the default branch became
    `master`, so the site would have deployed on no push at all — green CI,
    nothing published, no error anywhere.
    """
    branch = default_branch()
    if branch is None:  # detached with no remote, e.g. a tag build
        return []

    problems = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        # `on` is parsed as the boolean True by YAML 1.1
        triggers = spec.get("on") or spec.get(True) or {}
        push = triggers.get("push") if isinstance(triggers, dict) else None
        if not isinstance(push, dict):
            continue
        branches = push.get("branches")
        if branches and branch not in branches:
            problems.append(
                f"{path.relative_to(ROOT)}: push.branches={branches} "
                f"does not include the default branch {branch!r}"
            )
    return problems


BUTTON = re.compile(r"<button\b")
INTERACTIVE_CHILD = re.compile(r"<a\s|CommitLink")


def check_interactive_nesting() -> list[str]:
    """
    An <a> inside a <button> is invalid HTML and the click is swallowed.

    Shipped once: adding commit links turned every trend tile and dock row
    dead, because the row itself was the button.
    """
    problems = []
    for path in sorted((ROOT / "site/src").rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        for match in BUTTON.finditer(text):
            tail = text[match.start() :]
            close = tail.find("</button>")
            if close > 0 and INTERACTIVE_CHILD.search(tail[:close]):
                line = text[: match.start()].count("\n") + 1
                problems.append(f"{path.relative_to(ROOT)}:{line}: link nested inside a button")
    return problems


def check_no_hardcoded_base() -> list[str]:
    """
    The asset prefix belongs to the host, not to the repository.

    `PUBLIC_BASE=/molcrafts-ci/` was correct for GitHub Pages and silently
    wrong everywhere else: every script, stylesheet and font 404s and the
    page renders blank.
    """
    problems = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "PUBLIC_BASE" in line and "/molcrafts-ci/" in line:
                problems.append(
                    f"{path.relative_to(ROOT)}:{i}: PUBLIC_BASE pinned to a "
                    f"GitHub Pages subpath; the site is served at a root"
                )
    return problems


CROSS_REPO_TOKEN = re.compile(r"github\.token|secrets\.GITHUB_TOKEN")


def check_action_credentials() -> list[str]:
    """
    A composite action that writes to another repository cannot use GITHUB_TOKEN.

    The submit action shipped telling callers to notify molcrafts-ci with
    `GH_TOKEN: ${{ github.token }}`. That token is scoped to the repository
    running the workflow, so the call could only ever 404 — and because the
    step was a placeholder that echoed instead of calling, nothing failed.
    """
    problems = []
    for path in sorted((ROOT / "actions").rglob("action.yml")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CROSS_REPO_TOKEN.search(line):
                problems.append(
                    f"{path.relative_to(ROOT)}:{i}: GITHUB_TOKEN cannot reach "
                    f"another repository; take an App or PAT credential as an input"
                )
    return problems


CHECKS = {
    "workflow branch filters": check_workflow_branches,
    "cross-repository credentials": check_action_credentials,
    "interactive nesting": check_interactive_nesting,
    "hard-coded asset prefix": check_no_hardcoded_base,
}


def main() -> int:
    failed = 0
    for name, check in CHECKS.items():
        problems = check()
        if problems:
            failed += 1
            print(f"{name}:")
            for p in problems:
                print(f"  {p}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
