#!/usr/bin/env python3
"""The partner repositories this one is built and tested against.

``.github/partners.env`` names them, and this script resolves them for both
the workflows (``fetch``, through ``MolCrafts/molcrafts-ci/actions/setup-partners``)
and the git hooks (``check``, ``fetch``, ``run``), so a local gate and CI judge
against the same partner commit -- never whatever branch a developer's
sibling checkout is on.

Each partner is a ``<NAME>_REPOSITORY=owner/repo`` + ``<NAME>_REF`` pair,
checked out as the directory ``<name>`` (lower case). ``<NAME>_REF`` is a
branch, tag or full commit, used exactly as written. Committed dependency
manifests pin full commits so a push and its CI run use identical inputs.

Refs are used exactly as declared. No implicit branch matching or local sibling
fallback is allowed: coordinated changes update partners.env explicitly. Resolve
once, fetch that exact commit, and verify the checkout before building.

    partners.py check             cheap pre-push gate (login node is fine):
                                  every partner resolves, every path
                                  dependency resolves inside the layout CI
                                  checks out, and no workflow spells a partner
                                  commit of its own.
    partners.py fetch NAME DEST   check partner NAME out, resolved, into DEST.
    partners.py run -- CMD...     run CMD in CI's sibling layout: a copy of
                                  this working tree at <root>/<SELF> next to
                                  <root>/<partner> for every partner, with
                                  <root>/<SELF> as the working directory and
                                  $PARTNERS_SOURCE naming this checkout (to
                                  copy a result back, e.g. a relocked file).

``run`` keeps <root> under $MOLCRAFTS_PARTNER_CACHE when that is set (one
directory per repository, so the partner builds stay warm between pushes and
a partner checkout only moves to its newly resolved commit); otherwise <root>
is a temp directory removed afterwards.

partners.env holds ``KEY=VALUE`` lines and comments, nothing else. ``SELF``
names this repository's directory in the layout.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("MOLCRAFTS_PARTNERS_ROOT", Path.cwd())).resolve()
PINS = ROOT / ".github" / "partners.env"
SHA = re.compile(r"[0-9a-f]{40}")
# Build state inside the layout copy that a sync must not wipe.
KEEP = {".venv", ".tox", "target", ".pytest_cache", ".ruff_cache", ".cache"}


def die(msg: str) -> None:
    print(f"partners: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _clean_env() -> dict[str, str]:
    """os.environ without the repository variables git exports to a hook.

    A git hook runs with GIT_DIR, GIT_INDEX_FILE, ... pointing at the hooked
    repository. Left in place, every git call below -- and every git a build
    tool spawns (uv fetching a git dependency) -- would act on that
    repository instead of the partner checkout in its working directory.
    """
    names = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    ).stdout.split()
    env = {k: v for k, v in os.environ.items() if k not in names}
    # A fork that does not exist must fail ls-remote, not prompt for a login.
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


ENV = _clean_env()


def git(*args: str, cwd: Path | None = None, quiet: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        check=False,
        cwd=cwd,
        env=ENV,
        text=True,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
        encoding="utf-8",
    )


def load() -> dict[str, str]:
    env: dict[str, str] = {}
    if not PINS.is_file():
        return env
    for n, raw in enumerate(PINS.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or value != value.strip():
            die(f"{PINS.relative_to(ROOT)}:{n}: expected KEY=VALUE, got {raw!r}")
        env[key] = value
    return env


def partners(env: dict[str, str]) -> dict[str, tuple[str, str]]:
    found = {}
    for key, repo in env.items():
        if key.endswith("_REPOSITORY"):
            name = key.removesuffix("_REPOSITORY")
            ref = env.get(f"{name}_REF") or die(f"{name}_REPOSITORY has no {name}_REF")
            found[name] = (repo, ref)
    return found


def url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


@dataclass(frozen=True)
class Source:
    """Where a partner comes from: its repository, a git URL, the ref to fetch, its commit."""

    repo: str
    url: str
    ref: str
    commit: str
    why: str


def ls_remote(where: str, ref: str, must: bool = True) -> str | None:
    """The commit REF names at WHERE (a peeled tag's commit), or None.

    An unreachable WHERE is fatal when MUST, else None (a fork that does not exist).
    """
    got = git("ls-remote", where, ref, f"{ref}^{{}}", quiet=True)
    if got.returncode:
        if not must:
            return None
        die(f"cannot list {where}: {got.stderr.strip()}")
    found = dict(line.split("\t")[::-1] for line in got.stdout.splitlines() if "\t" in line)
    return found.get(f"{ref}^{{}}") or found.get(ref)


def resolve(name: str, repo: str, ref: str) -> Source:
    """Resolve only the declared ref, independent of the caller's branch."""
    remote = url(repo)
    if SHA.fullmatch(ref):
        return Source(repo, remote, ref, ref, "pinned commit")
    branch = ref if ref.startswith("refs/heads/") else f"refs/heads/{ref}"
    tag = ref if ref.startswith("refs/tags/") else f"refs/tags/{ref}"
    tip = ls_remote(remote, branch)
    if tip is not None:
        return Source(repo, remote, branch, tip, f"declared branch {ref}")
    tip = ls_remote(remote, tag) or die(f"{name}: {repo} has no branch or tag {ref!r}")
    return Source(repo, remote, tag, tip, f"declared tag {ref}")


def resolved() -> dict[str, Source]:
    return {name: resolve(name, repo, ref) for name, (repo, ref) in partners(load()).items()}


def fetch(name: str, src: Source, dest: Path) -> None:
    """Check SRC out into DEST, reusing DEST when it already is that commit."""
    if (dest / ".git").is_dir():
        head = git("rev-parse", "HEAD", cwd=dest, quiet=True).stdout.strip()
        dirty = git("status", "--porcelain", "--untracked-files=no", cwd=dest, quiet=True).stdout
        if head == src.commit and not dirty:
            print(f"partners: {name} is {src.commit[:12]} ({src.why})", file=sys.stderr)
            return
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").is_dir():
        git("init", "-q", cwd=dest)
    print(f"partners: fetching {name} {src.commit[:12]} ({src.why}) -> {dest}", file=sys.stderr)
    if git("fetch", "-q", "--depth=1", src.url, src.commit, cwd=dest).returncode:
        die(f"cannot fetch {name} {src.url} {src.ref}")
    if git("checkout", "-q", "--force", "--detach", "FETCH_HEAD", cwd=dest).returncode:
        die(f"cannot check out {name} {src.url} {src.ref}")
    actual = git("rev-parse", "HEAD", cwd=dest, quiet=True).stdout.strip()
    if actual != src.commit:
        die(f"{name}: expected {src.commit}, checked out {actual}")


def commit_exists(where: str, commit: str) -> bool:
    """Whether WHERE has COMMIT: fetch that one commit object (no trees, no blobs)."""
    with tempfile.TemporaryDirectory() as tmp:
        git("init", "-q", "--bare", cwd=Path(tmp))
        got = git(
            "fetch", "-q", "--depth=1", "--filter=tree:0", where, commit, cwd=Path(tmp), quiet=True
        )
        return got.returncode == 0


def tracked(basename: str) -> list[Path]:
    out = git("ls-files", "-z", cwd=ROOT, quiet=True).stdout
    return [
        ROOT / p for p in out.split("\0") if p and Path(p).name == basename and (ROOT / p).is_file()
    ]


def path_deps() -> list[tuple[Path, str, str]]:
    """(manifest, dependency, path) for every path dependency in a tracked manifest."""
    found = []
    for manifest in tracked("pyproject.toml"):
        sources = (
            tomllib.loads(manifest.read_text(encoding="utf-8"))
            .get("tool", {})
            .get("uv", {})
            .get("sources", {})
        )
        for dep, spec in sources.items():
            for entry in spec if isinstance(spec, list) else [spec]:
                if isinstance(entry, dict) and "path" in entry:
                    found.append((manifest, dep, entry["path"]))

    def tables(doc: dict) -> list[dict]:
        out = [doc.get(k, {}) for k in ("dependencies", "dev-dependencies", "build-dependencies")]
        out.append(doc.get("workspace", {}).get("dependencies", {}))
        for target in doc.get("target", {}).values():
            out += [
                target.get(k, {})
                for k in ("dependencies", "dev-dependencies", "build-dependencies")
            ]
        out += list(doc.get("patch", {}).values())
        return out

    for manifest in tracked("Cargo.toml"):
        for table in tables(tomllib.loads(manifest.read_text(encoding="utf-8"))):
            for dep, spec in table.items():
                if isinstance(spec, dict) and "path" in spec:
                    found.append((manifest, dep, spec["path"]))
    return found


def check() -> int:
    failures = []
    found = resolved()
    for name, src in found.items():
        if src.ref == src.commit and not commit_exists(src.url, src.commit):
            failures.append(
                f"{name}: {src.repo}@{src.commit} does not exist (CI cannot check it out)"
            )
            continue
        print(f"ok: {name} {src.repo} -> {src.commit} ({src.why})")

    layout = {name.lower() for name in found}
    for manifest, dep, raw in path_deps():
        target = Path(os.path.normpath(manifest.parent / raw))
        where = f"{manifest.relative_to(ROOT)}: {dep} = {{ path = {raw!r} }}"
        try:
            target.relative_to(ROOT)
            continue
        except ValueError:
            pass
        try:
            first = target.relative_to(ROOT.parent).parts[0]
        except ValueError:
            first = None
        if first in layout:
            continue
        failures.append(
            f"{where} resolves outside this repository, to {first or target!s}, which CI "
            f"never checks out (partners in .github/partners.env: {sorted(layout) or 'none'})"
        )

    for wf in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"\s*ref:\s*['\"]?[0-9a-f]{40}\b", line):
                failures.append(
                    f"{wf.relative_to(ROOT)}:{n}: a literal partner commit; name the partner "
                    "in .github/partners.env and check it out with `partners.py fetch`"
                )

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    return 1 if failures else 0


def sync(dest: Path) -> None:
    """Make DEST a copy of this working tree (tracked + untracked, not ignored)."""
    listed = git(
        "ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=ROOT, quiet=True
    ).stdout
    files = {p for p in listed.split("\0") if p and os.path.lexists(ROOT / p)}
    dest.mkdir(parents=True, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(dest, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in KEEP]
        for f in filenames:
            rel = os.path.relpath(os.path.join(dirpath, f), dest)
            if rel not in files:
                os.unlink(os.path.join(dirpath, f))
    for rel in sorted(files):
        src, dst = ROOT / rel, dest / rel
        if src.is_symlink():
            if dst.is_symlink() and os.readlink(dst) == os.readlink(src):
                continue
            dst.unlink(missing_ok=True)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(os.readlink(src), dst)
            continue
        s = src.stat()
        if dst.is_file() and not dst.is_symlink():
            d = dst.stat()
            if (d.st_size, d.st_mtime_ns) == (s.st_size, s.st_mtime_ns):
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def run(cmd: list[str]) -> int:

    env = load()
    me = env.get("SELF") or die("partners.env names no SELF")
    found = resolved()
    cache = os.environ.get("MOLCRAFTS_PARTNER_CACHE")
    key = hashlib.sha256(repr(sorted(partners(env).items())).encode()).hexdigest()
    root = (
        Path(cache) / f"{me}-{key[:12]}"
        if cache
        else Path(tempfile.mkdtemp(prefix=f"{me}-partners-"))
    )
    root.mkdir(parents=True, exist_ok=True)
    try:
        with open(root / ".lock", "w", encoding="utf-8") as lock:
            if os.name == "nt":
                import msvcrt

                lock.write("0")
                lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock, fcntl.LOCK_EX)
            for name, src in found.items():
                fetch(name, src, root / name.lower())
            sync(root / me)
            print(f"partners: running in {root / me}: {' '.join(cmd)}", file=sys.stderr)
            env_out = dict(ENV, PARTNERS_SOURCE=str(ROOT))
            return subprocess.run(cmd, check=False, cwd=root / me, env=env_out).returncode
    finally:
        if not cache:
            shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str]) -> int:
    if argv == ["check"]:
        return check()
    if argv == ["fetch-all"]:
        for name, source in resolved().items():
            dest = ROOT.parent / name.lower()
            fetch(name, source, dest)
            if output := os.environ.get("GITHUB_ENV"):
                with open(output, "a", encoding="utf-8", newline="\n") as stream:
                    stream.write(f"{name}_DIR={dest}\n")
        return 0
    if argv[:1] == ["fetch-one"] and len(argv) == 4:
        repo, ref, dest = argv[1:]
        fetch(repo, resolve(repo, repo, ref), Path(dest))
        return 0
    if argv[:1] == ["fetch"] and len(argv) == 3:
        found = resolved()
        name = argv[1].upper()
        if name not in found:
            die(f"no partner {name} in .github/partners.env (have: {sorted(found)})")
        fetch(name, found[name], Path(argv[2]))
        return 0
    if argv[:2] == ["run", "--"] and len(argv) > 2:
        return run(argv[2:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
