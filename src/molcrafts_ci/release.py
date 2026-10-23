"""What a release and a nightly need beyond building.

- `release_ready`: on a `v*` tag, the tag is on master, names the version
  being released, and its commit passed `ci` (the push to master ran it; the
  release waits for that run instead of repeating it).
- `nightly_version` and `stamp_nightly`: turn the checkout into the nightly
  package described by the `[nightly]` table of `.github/ci.toml`.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import tomllib
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from molcrafts_ci.config import Nightly

CI_WORKFLOW = "ci"


def ci_runs(repository: str, sha: str, token: str) -> list[dict]:
    """The push-triggered runs of the `ci` workflow for one commit."""
    url = (
        f"https://api.github.com/repos/{repository}/actions/runs"
        f"?head_sha={sha}&event=push&per_page=100"
    )
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        runs = json.load(response)["workflow_runs"]
    return [r for r in runs if r["name"] == CI_WORKFLOW]


def wait_for_ci(
    repository: str,
    sha: str,
    token: str,
    *,
    timeout: float = 90 * 60,
    log: Callable[[str], None] = print,
    runs: Callable[[str, str, str], list[dict]] = ci_runs,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Return once the newest `ci` run of SHA succeeded; raise if it did not."""
    deadline = time.monotonic() + timeout
    while True:
        found = sorted(runs(repository, sha, token), key=lambda r: r["created_at"])
        latest = found[-1] if found else None
        if latest and latest["status"] == "completed":
            if latest["conclusion"] != "success":
                raise RuntimeError(f"{sha[:7]}: ci {latest['conclusion']}: {latest['html_url']}")
            log(f"{sha[:7]}: ci passed ({latest['html_url']})")
            return
        state = "ci to start" if latest is None else f"ci ({latest['html_url']})"
        if time.monotonic() > deadline:
            raise RuntimeError(f"{sha[:7]}: gave up waiting for {state}")
        log(f"waiting for {state}")
        sleep(60)


def dist_version(dist: Path) -> str:
    """The single version of the wheels and sdists in DIST."""
    versions = set()
    for path in dist.iterdir():
        if path.suffix == ".whl":
            versions.add(path.name.split("-")[1])
        elif path.name.endswith(".tar.gz"):
            versions.add(path.name.removesuffix(".tar.gz").rsplit("-", 1)[1])
    if len(versions) != 1:
        raise RuntimeError(f"{dist} holds {len(versions)} versions: {sorted(versions) or 'none'}")
    return versions.pop()


VERSION_LINE = re.compile(r'^(?P<lead>\s*(?:__version__|version)\s*=\s*)"(?P<version>[^"]+)"', re.M)


def file_version(path: Path) -> str:
    """The version a Cargo.toml, a pyproject.toml or a `version = "..."` file states."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        data = tomllib.loads(text)
        for table in (
            data.get("package"),
            data.get("workspace", {}).get("package"),
            data.get("project"),
        ):
            if isinstance(table, dict) and isinstance(table.get("version"), str):
                return table["version"]
        raise RuntimeError(f"{path} states no version")
    match = VERSION_LINE.search(text)
    if not match:
        raise RuntimeError(f'no `version = "..."` line in {path}')
    return match["version"]


def release_ready(
    version: str,
    *,
    ref: str,
    repository: str,
    sha: str,
    token: str,
    log: Callable[[str], None] = print,
    wait: Callable[..., None] = wait_for_ci,
) -> None:
    """On a `v*` tag: the tag is VERSION, is on master, and its commit passed ci.

    Any other ref is a dry run of the release and passes.
    """
    if not ref.startswith("refs/tags/"):
        log(f"{ref} is not a tag: a dry run, version {version}")
        return
    tag = ref.removeprefix("refs/tags/")
    if tag != f"v{version}":
        raise RuntimeError(f"the tag is {tag}, the version is {version}")
    on_master = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/master"], check=False
    )
    if on_master.returncode:
        raise RuntimeError(f"{tag} is not on master; merge dev into master and tag that")
    wait(repository, sha, token, log=log)
    log(f"{tag} is ready")


def _project_table(text: str) -> tuple[int, int]:
    """Start and end offsets of the [project] table's body in a pyproject.toml."""
    start = re.search(r"(?m)^\[project\]\s*$", text)
    if not start:
        raise RuntimeError("pyproject.toml has no [project] table")
    end = re.compile(r"(?m)^\[").search(text, start.end())
    return start.end(), end.start() if end else len(text)


def nightly_version(root: Path, nightly: Nightly, *, now: datetime | None = None) -> str:
    """`<version>.dev<YYYYmmddHHMM>`, computed once for every OS of a nightly."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d%H%M")
    source = root / (nightly.version_file or nightly.pyproject)
    return f"{file_version(source)}.dev{stamp}"


def stamp_nightly(root: Path, nightly: Nightly, version: str) -> None:
    """Rename the package and its partners to their nightly names, at VERSION.

    The version is written into [project] as a static version (a `dynamic`
    version, read from Cargo.toml or a module, would read the release's).
    `[tool.uv.sources]` is dropped, so the package builds against what it
    declares, as a user would install it.
    """
    pyproject = root / nightly.pyproject
    text = pyproject.read_text(encoding="utf-8")
    start, end = _project_table(text)
    body = text[start:end]
    body, renamed = re.subn(
        r'(?m)^name\s*=\s*"[^"]+"', f'name = "{nightly.package}"', body, count=1
    )
    if not renamed:
        raise RuntimeError(f'no `name = "..."` in [project] of {pyproject}')
    body = re.sub(r'(?m)^version\s*=\s*"[^"]*"\n', "", body)
    body = re.sub(
        r"(?m)^dynamic\s*=\s*\[(?P<items>[^\]]*)\]\n",
        lambda m: _without_version(m["items"]),
        body,
    )
    body = re.sub(r'(?m)^(name\s*=\s*"[^"]+"\n)', rf'\1version = "{version}"\n', body, count=1)
    text = text[:start] + body + text[end:]

    for package, replacement in nightly.rename.items():
        # The nightly of a partner keeps the minor line the release declared:
        # "molcrafts-molrs>=0.19.0,<0.20" -> "molcrafts-molrs-nightly>=0.19.0.dev0".
        dependency = re.compile(rf'"{re.escape(package)}(?:\[[^\]]*\])?\s*(?P<spec>[<>=!~][^"]*)?"')

        def nightly_dependency(m: re.Match[str], replacement: str = replacement) -> str:
            floor = re.search(r">=\s*(\d+)\.(\d+)", m["spec"] or "")
            minimum = f"{floor[1]}.{floor[2]}.0.dev0" if floor else "0.0.0.dev0"
            return f'"{replacement}>={minimum}"'

        text, count = dependency.subn(nightly_dependency, text)
        if not count:
            raise RuntimeError(f"nightly.rename: {package} is not a dependency in {pyproject}")
    text = re.sub(r"(?ms)^\[tool\.uv\.sources\]\n.*?(?=^\[|\Z)", "", text)
    pyproject.write_text(text, encoding="utf-8")


def _without_version(items: str) -> str:
    kept = [
        i.strip() for i in items.split(",") if i.strip() and i.strip().strip("\"'") != "version"
    ]
    return f"dynamic = [{', '.join(kept)}]\n" if kept else ""
