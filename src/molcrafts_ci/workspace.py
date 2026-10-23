"""Partner repositories, checked out next to this one as `../<name>`.

CI clones each partner at the branch or tag `.github/ci.toml` names. Locally
the sibling checkout a developer already has is used as it is; `molci check`
says which branch and commit that is, so a difference from CI is visible
rather than silent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from molcrafts_ci.config import Config, Partner


def clean_git_env() -> dict[str, str]:
    """os.environ without the variables git exports to a hook (GIT_DIR, ...).

    Left in place, every git a check runs, and every git a build tool spawns,
    would act on the repository being committed instead of its own directory.
    """
    names = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, check=False
    ).stdout.split()
    env = {key: value for key, value in os.environ.items() if key not in names}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def partner_dir(root: Path, partner: Partner) -> Path:
    return root.resolve().parent / partner.name


def describe(path: Path) -> str:
    """`dev @ 1a2b3c4` for a checkout, or why it is not one."""

    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            env=clean_git_env(),
            check=False,
        )
        return out.stdout.strip()

    if not (path / ".git").exists():
        return "not a git checkout"
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    commit = git("rev-parse", "--short", "HEAD") or "?"
    dirty = " (local changes)" if git("status", "--porcelain", "--untracked-files=no") else ""
    return f"{'detached' if branch == 'HEAD' else branch} @ {commit}{dirty}"


def fetch(root: Path, config: Config, *, log: Callable[[str], None] = print) -> None:
    """Clone every partner that is not checked out yet; leave existing ones alone."""
    for partner in config.partners:
        dest = partner_dir(root, partner)
        if dest.exists():
            log(f"{partner.name}: ../{partner.name} already there ({describe(dest)})")
            continue
        log(f"{partner.name}: cloning {partner.repository}@{partner.ref} into ../{partner.name}")
        done = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                partner.ref,
                partner.url,
                str(dest),
            ],
            env=clean_git_env(),
            check=False,
        )
        if done.returncode:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"cannot clone {partner.repository}@{partner.ref}")


def require(root: Path, config: Config, *, log: Callable[[str], None] = print) -> None:
    """Fail unless every partner is checked out; say which state each one is in."""
    missing = []
    for partner in config.partners:
        dest = partner_dir(root, partner)
        if not dest.exists():
            missing.append(partner)
            continue
        log(f"{partner.name}: ../{partner.name} is {describe(dest)} (CI uses {partner.ref})")
    if missing:
        names = ", ".join(f"../{p.name}" for p in missing)
        raise RuntimeError(f"missing partner checkout {names}; run `molci partners` to clone it")


def rust_toolchains(root: Path, config: Config, *, log: Callable[[str], None] = print) -> list[str]:
    """Install each pinned Rust toolchain; return the cargo workspaces to cache."""
    dirs = [root.resolve()] + [partner_dir(root, p) for p in config.partners]
    workspaces = []
    for path in dirs:
        rel = os.path.relpath(path, root.resolve())
        if (path / "rust-toolchain.toml").is_file() or (path / "rust-toolchain").is_file():
            log(f"rust: toolchain of {rel}")
            subprocess.run(["rustup", "toolchain", "install"], cwd=path, check=True)
        if (path / "Cargo.toml").is_file():
            workspaces.append(f"{Path(rel).as_posix()} -> target")
    return workspaces


def stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
