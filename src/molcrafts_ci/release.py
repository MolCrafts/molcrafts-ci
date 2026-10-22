"""The publishing contract: where a repository may publish, and how.

A repository declares what it publishes in ``.github/release.toml``, one table
per target, each listing the packages it uploads::

    [pypi]
    packages = ["molcrafts-molrs"]

    [pypi-nightly]
    packages = ["molcrafts-molrs-nightly"]

    [github-release]

Everything else follows from the target's name, and nothing else may differ
between repositories:

* the workflow file that publishes it (``release.yml`` for a stable target,
  ``nightly.yml`` for its ``-nightly`` twin, ``deploy.yml`` for a site), which
  is also the file a registry's trusted publisher names;
* the GitHub environment the publishing job enters, named like the target;
* the secrets that environment must hold (none for a trusted publisher).

``actions/check-workflows`` holds the workflows to this table and
``molci audit`` holds the repository's GitHub settings to it.

Standard library only: check-workflows loads this file by path from a PEP 723
script that brings PyYAML and nothing else.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

RELEASE_TOML = Path(".github") / "release.toml"
NIGHTLY = "-nightly"


@dataclass(frozen=True)
class Target:
    """One place a repository publishes to."""

    name: str
    workflow: str  # the file stem that publishes it
    environment: str | None  # the GitHub environment its job enters
    secrets: tuple[str, ...] = ()  # what that environment must hold
    trusted: str | None = None  # the registry whose trusted publisher binds the workflow
    has_packages: bool = True  # whether the table lists packages

    @property
    def workflow_file(self) -> str:
        return f"{self.workflow}.yml"


# The stable targets. Each has a `-nightly` twin published from nightly.yml
# through an environment of the twin's name (see `target`).
_STABLE = {
    t.name: t
    for t in (
        Target("pypi", "release", "pypi", trusted="pypi"),
        Target("npm", "release", "npm", trusted="npm"),
        Target("crates-io", "release", "crates-io", trusted="crates-io"),
        Target("vscode-marketplace", "release", "vscode-marketplace", ("VSCE_PAT", "OVSX_PAT")),
        Target("github-release", "release", None, has_packages=False),
        Target("github-pages", "deploy", "github-pages", has_packages=False),
        Target(
            "cloudflare-pages",
            "deploy",
            "cloudflare-pages",
            ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"),
        ),
    )
}

# Secrets that publish somewhere: they belong in their target's environment,
# never at the repository level where every job can read them.
PUBLISH_SECRETS = frozenset(
    {s for t in _STABLE.values() for s in t.secrets}
    | {"PYPI_API_TOKEN", "PYPI_TOKEN", "NPM_TOKEN", "CARGO_REGISTRY_TOKEN", "CRATES_IO_TOKEN"}
)

# Environments GitHub itself creates for a feature, not for publishing.
PLATFORM_ENVIRONMENTS = frozenset({"copilot"})


def target(name: str) -> Target:
    """The target named ``name`` (a stable one, or its ``-nightly`` twin).

    Raises:
        KeyError: ``name`` is no MolCrafts publishing target.
    """
    if name in _STABLE:
        return _STABLE[name]
    base = name.removesuffix(NIGHTLY)
    if name.endswith(NIGHTLY) and base in _STABLE:
        stable = _STABLE[base]
        env = stable.environment
        return Target(
            name,
            "nightly",
            None if env is None else f"{env}{NIGHTLY}",
            stable.secrets,
            stable.trusted,
            stable.has_packages,
        )
    known = ", ".join(sorted(_STABLE))
    raise KeyError(
        f"`{name}` is not a publishing target (known: {known}, and their -nightly twins)"
    )


def known(name: str) -> bool:
    try:
        target(name)
    except KeyError:
        return False
    return True


@dataclass(frozen=True)
class Declared:
    """One table of release.toml."""

    target: Target
    packages: tuple[str, ...]


def read_release(root: Path) -> list[Declared] | None:
    """The targets ``root/.github/release.toml`` declares, or None without one.

    Raises:
        ValueError: The file is not TOML, names an unknown target, or a table's
            ``packages`` is missing / present where the target has none.
    """
    path = root / RELEASE_TOML
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{RELEASE_TOML}: {exc}") from exc
    out = []
    for name, table in data.items():
        if not isinstance(table, dict):
            raise ValueError(f"{RELEASE_TOML}: `{name}` must be a table")
        try:
            tgt = target(name)
        except KeyError as exc:
            raise ValueError(f"{RELEASE_TOML}: {exc.args[0]}") from exc
        packages = table.get("packages")
        extra = set(table) - {"packages"}
        if extra:
            raise ValueError(f"{RELEASE_TOML}: [{name}] has unknown keys {sorted(extra)}")
        if tgt.has_packages:
            if not (
                isinstance(packages, list)
                and packages
                and all(isinstance(p, str) for p in packages)
            ):
                raise ValueError(f'{RELEASE_TOML}: [{name}] needs packages = ["..."]')
        elif packages is not None:
            raise ValueError(f"{RELEASE_TOML}: [{name}] publishes no packages; drop `packages`")
        out.append(Declared(tgt, tuple(packages or ())))
    return out
