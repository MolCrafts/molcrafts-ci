"""`.github/ci.toml`: what a repository checks, in one human-readable file.

    [env]                                  # optional, set for every check
    PYTHONWARNDEFAULTENCODING = "1"

    [tools]                                # optional defaults for every check
    python = "3.12"                        # or a list: the first runs on every OS
    node = "site/.nvmrc"                   # a version, or a path to an .nvmrc
    rust = true                            # rust-toolchain.toml of this repo and partners

    [partners]                             # optional; without it dependencies
    molrs = "MolCrafts/molrs@dev"          # resolve normally (PyPI, crates.io)

    [check.test]
    run = "uv run pytest"                  # a command, or a list of commands
    stage = "pre-push"                     # pre-commit | pre-push | release
    os = ["linux", "macos", "windows"]     # default: linux
    junit = ".ci-out/junit.xml"            # optional: summarised in the run
    coverage = ".ci-out/coverage.json"     # optional: coverage.py JSON or LCOV

    [dashboard]                            # optional: publish tests/coverage
    project = "molpy"
    branch = "dev"                         # pushes to this branch are history

    [nightly]                              # optional: python-nightly.yml
    package = "molcrafts-molpy-nightly"
    version-file = "src/molpy/version.py"
    rename = { "molcrafts-molrs" = "molcrafts-molrs-nightly" }

Every key is checked; a typo is an error that names the file and the key.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(".github") / "ci.toml"
STAGES = ("pre-commit", "pre-push", "release")
OSES = {"linux": "ubuntu-latest", "macos": "macos-latest", "windows": "windows-latest"}
NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
PARTNER = re.compile(r"(?P<repository>[\w.-]+/[\w.-]+)@(?P<ref>[\w./-]+)")


class ConfigError(ValueError):
    """`.github/ci.toml` is missing or says something this version cannot read."""


@dataclass(frozen=True)
class Partner:
    """A repository checked out next to this one, as `../<name>`, at a branch or tag."""

    name: str
    repository: str
    ref: str

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repository}.git"


@dataclass(frozen=True)
class Check:
    name: str
    run: tuple[str, ...]
    stage: str = "pre-push"
    os: tuple[str, ...] = ("linux",)
    python: tuple[str, ...] = ()
    node: str | None = None
    rust: bool = False
    junit: str | None = None
    coverage: str | None = None


@dataclass(frozen=True)
class Dashboard:
    project: str
    branch: str = "master"


@dataclass(frozen=True)
class Nightly:
    package: str
    version_file: str | None = None
    rename: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    path: Path
    env: dict[str, str] = field(default_factory=dict)
    partners: tuple[Partner, ...] = ()
    checks: tuple[Check, ...] = ()
    dashboard: Dashboard | None = None
    nightly: Nightly | None = None

    def check(self, name: str) -> Check:
        for check in self.checks:
            if check.name == name:
                return check
        raise ConfigError(f"{self.path}: no [check.{name}] (have: {self.check_names()})")

    def check_names(self) -> str:
        return ", ".join(c.name for c in self.checks) or "none"


def load(root: Path) -> Config:
    """Read `<root>/.github/ci.toml`."""
    path = root / CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"{path} does not exist; it lists what this repository checks")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return parse(data, path)


def parse(data: dict[str, Any], path: Path) -> Config:
    reader = _Reader(path)
    reader.keys(data, "", {"env", "tools", "partners", "check", "dashboard", "nightly"})
    env = reader.strings(data.get("env", {}), "env")
    tools = data.get("tools", {})
    reader.keys(tools, "tools", {"python", "node", "rust"})
    defaults = {
        "python": reader.versions(tools.get("python"), "tools.python"),
        "node": reader.optional_str(tools.get("node"), "tools.node"),
        "rust": reader.boolean(tools.get("rust", False), "tools.rust"),
    }
    partners = tuple(
        reader.partner(name, spec) for name, spec in reader.table(data, "partners").items()
    )
    checks = tuple(
        reader.check(name, spec, defaults) for name, spec in reader.table(data, "check").items()
    )
    if not checks:
        raise ConfigError(f"{path}: no [check.<name>] table; list at least one check")
    return Config(
        path=path,
        env=env,
        partners=partners,
        checks=checks,
        dashboard=reader.dashboard(data.get("dashboard"), checks),
        nightly=reader.nightly(data.get("nightly")),
    )


class _Reader:
    """Typed access to the parsed TOML, with errors that name the key."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def fail(self, key: str, message: str) -> ConfigError:
        return ConfigError(f"{self.path}: {key}: {message}")

    def keys(self, value: Any, where: str, allowed: set[str]) -> None:
        if not isinstance(value, dict):
            raise self.fail(where, "must be a table")
        unknown = sorted(set(value) - allowed)
        if unknown:
            prefix = f"{where}." if where else ""
            raise self.fail(
                prefix + unknown[0], f"unknown key (allowed: {', '.join(sorted(allowed))})"
            )

    def table(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        value = data.get(key, {})
        if not isinstance(value, dict):
            raise self.fail(key, "must be a table")
        return value

    def strings(self, value: Any, key: str) -> dict[str, str]:
        if not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values()):
            raise self.fail(key, 'must be a table of strings, e.g. NAME = "value"')
        return dict(value)

    def optional_str(self, value: Any, key: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise self.fail(key, "must be a non-empty string")
        return value

    def boolean(self, value: Any, key: str) -> bool:
        if not isinstance(value, bool):
            raise self.fail(key, "must be true or false")
        return value

    def versions(self, value: Any, key: str) -> tuple[str, ...]:
        if value is None:
            return ()
        items = [value] if isinstance(value, str) else value
        if not isinstance(items, list) or not items or not all(isinstance(v, str) for v in items):
            raise self.fail(key, 'must be a version or a list of versions, e.g. "3.12"')
        return tuple(items)

    def partner(self, name: str, spec: Any) -> Partner:
        key = f"partners.{name}"
        if not NAME.fullmatch(name):
            raise self.fail(key, "a partner name is lower case, digits and dashes")
        match = PARTNER.fullmatch(spec) if isinstance(spec, str) else None
        if not match:
            raise self.fail(key, 'must read "<owner>/<repository>@<branch or tag>"')
        return Partner(name=name, repository=match["repository"], ref=match["ref"])

    def check(self, name: str, spec: Any, defaults: dict[str, Any]) -> Check:
        key = f"check.{name}"
        if not NAME.fullmatch(name):
            raise self.fail(key, "a check name is lower case, digits and dashes")
        self.keys(spec, key, {"run", "stage", "os", "python", "node", "rust", "junit", "coverage"})
        run = spec.get("run")
        commands = [run] if isinstance(run, str) else run
        if (
            not isinstance(commands, list)
            or not commands
            or not all(isinstance(c, str) and c.strip() for c in commands)
        ):
            raise self.fail(f"{key}.run", "must be a command or a list of commands")
        stage = spec.get("stage", "pre-push")
        if stage not in STAGES:
            raise self.fail(f"{key}.stage", f"must be one of {', '.join(STAGES)}")
        oses = spec.get("os", ["linux"])
        oses = [oses] if isinstance(oses, str) else oses
        if not isinstance(oses, list) or not oses or any(o not in OSES for o in oses):
            raise self.fail(f"{key}.os", f"must list some of {', '.join(OSES)}")
        python = self.versions(spec.get("python"), f"{key}.python") or defaults["python"]
        return Check(
            name=name,
            run=tuple(commands),
            stage=stage,
            os=tuple(dict.fromkeys(oses)),
            python=python,
            node=self.optional_str(spec.get("node"), f"{key}.node") or defaults["node"],
            rust=self.boolean(spec.get("rust", defaults["rust"]), f"{key}.rust"),
            junit=self.optional_str(spec.get("junit"), f"{key}.junit"),
            coverage=self.optional_str(spec.get("coverage"), f"{key}.coverage"),
        )

    def dashboard(self, spec: Any, checks: tuple[Check, ...]) -> Dashboard | None:
        if spec is None:
            return None
        self.keys(spec, "dashboard", {"project", "branch"})
        project = self.optional_str(spec.get("project"), "dashboard.project")
        if project is None:
            raise self.fail("dashboard.project", "is required")
        if not any(c.junit or c.coverage for c in checks):
            raise self.fail("dashboard", "needs a check with `junit` or `coverage` to publish")
        branch = self.optional_str(spec.get("branch"), "dashboard.branch") or "master"
        return Dashboard(project=project, branch=branch)

    def nightly(self, spec: Any) -> Nightly | None:
        if spec is None:
            return None
        self.keys(spec, "nightly", {"package", "version-file", "rename"})
        package = self.optional_str(spec.get("package"), "nightly.package")
        if package is None:
            raise self.fail("nightly.package", "is required")
        return Nightly(
            package=package,
            version_file=self.optional_str(spec.get("version-file"), "nightly.version-file"),
            rename=self.strings(spec.get("rename", {}), "nightly.rename"),
        )
