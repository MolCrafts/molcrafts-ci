"""Profile selection is by name. The hook reads profiles/<name>.yml."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / "hooks" / "ci.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CI), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_profiles_are_named() -> None:
    names = sorted(p.stem for p in (ROOT / "profiles").glob("*.yml"))
    assert names == ["node", "node-python", "python", "rust-python"]


def test_list_lint_gates_for_node_python() -> None:
    result = run("--profile", "node-python", "--area", "lint", "--list")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["workflows", "biome", "guards", "typecheck", "test-core"]


def test_unknown_profile_names_the_choices() -> None:
    result = run("--profile", "nope", "--area", "lint", "--list")
    assert result.returncode != 0
    assert "node-python" in result.stderr or "node-python" in result.stdout


def test_describe_reports_setup() -> None:
    result = run("--profile", "node-python", "--describe", "guards")
    assert result.returncode == 0, result.stderr
    meta = json.loads(result.stdout)
    assert meta["setup"] == ["node-no-install", "python", "partners"]
    assert "uv lock --check" in meta["run"]


def load_ci():
    spec = importlib.util.spec_from_file_location("molcrafts_ci_hook", CI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_leading_double_dash_is_ignored(capsys: pytest.CaptureFixture[str]) -> None:
    ci = load_ci()
    assert ci.main(["--profile", "node-python", "--list"]) == 0
    plain = capsys.readouterr()
    assert ci.main(["--", "--profile", "node-python", "--list"]) == 0
    dashed = capsys.readouterr()
    assert dashed == plain
    assert "workflows" in json.loads(plain.out)
