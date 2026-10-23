"""What python-release.yml and python-nightly.yml need beyond `uv build`.

- `wait_for_ci`: a release tag's commit must have passed `ci` (its push to
  master ran it); the release waits for that run instead of repeating it.
- `dist_version`: the version the built files carry, to compare with the tag.
- `stamp_nightly`: turn the checkout into the nightly package, the
  `[nightly]` table of `.github/ci.toml`.
"""

from __future__ import annotations

import json
import re
import time
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


def stamp_nightly(root: Path, nightly: Nightly, *, now: datetime | None = None) -> str:
    """Rename the package, make its version `<base>.dev<YYYYmmddHHMM>`, use nightly partners.

    Returns the nightly version. `[tool.uv.sources]` is dropped, so the
    package builds against what it declares, as a user would install it.
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d%H%M")
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    version_path = root / nightly.version_file if nightly.version_file else pyproject
    version_text = text if version_path == pyproject else version_path.read_text(encoding="utf-8")
    match = VERSION_LINE.search(version_text)
    if not match:
        raise RuntimeError(f'no `version = "..."` line in {version_path}')
    version = f"{match['version']}.dev{stamp}"
    version_text = VERSION_LINE.sub(lambda m: f'{m["lead"]}"{version}"', version_text, count=1)
    if version_path == pyproject:
        text = version_text
    else:
        version_path.write_text(version_text, encoding="utf-8")

    text, renamed = re.subn(
        r'(?m)^name\s*=\s*"[^"]+"', f'name = "{nightly.package}"', text, count=1
    )
    if not renamed:
        raise RuntimeError(f'no `name = "..."` line in {pyproject}')
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
    return version
