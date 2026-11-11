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
    assert names == ["node", "node-python", "python", "rust-python", "rust-python-v2"]


def test_list_lint_gates_for_node_python() -> None:
    result = run("--profile", "node-python", "--area", "lint", "--list")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["workflows", "biome", "guards", "typecheck"]


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


@pytest.mark.parametrize("path", sorted((ROOT / "profiles").glob("*.yml")), ids=lambda p: p.stem)
def test_build_gate_precedes_its_readers(path: Path) -> None:
    """A gate with `setup: [build]` reads the `build` gate's artifacts.

    In the same stage the `build` gate runs before it, so a local stage builds
    once and nothing after it rebuilds.
    """
    ci = load_ci()
    gates = ci.load_profile(path.stem)["gates"]
    order = [g["id"] for g in gates]
    for gate in gates:
        if "build" not in (gate.get("setup") or []):
            continue
        assert "build" in order, f"{path.stem}: {gate['id']} needs a build gate"
        build = gates[order.index("build")]
        assert build["stage"] == gate["stage"], (
            f"{path.stem}: {gate['id']} and build differ in stage"
        )
        assert order.index("build") < order.index(gate["id"]), (
            f"{path.stem}: build after {gate['id']}"
        )


def test_node_python_runs_each_check_once() -> None:
    """molvis: one build, one typecheck, one run of each suite (no test-core)."""
    ci = load_ci()
    gates = ci.load_profile("node-python")["gates"]
    assert [g["id"] for g in gates if g["stage"] == "pre-push"] == [
        "build",
        "typecheck",
        "js",
        "vsc-ext",
        "python",
        "docs",
    ]
    later = " ".join(str(g["run"]) for g in gates if g["id"] != "build")
    assert "npm run build" not in later


def test_downloaded_hook_uses_persistent_uv_tool_cache(tmp_path, monkeypatch):
    ci = load_ci()
    monkeypatch.setattr(ci, "__file__", str(tmp_path / "download" / "ci.py"))
    monkeypatch.setattr(ci, "scrub_git_env", lambda: None)
    monkeypatch.setenv("CI_REF", "a" * 40)
    calls = []
    monkeypatch.setattr(ci.os, "execvp", lambda name, argv: calls.append((name, argv)))
    ci.ci_root(tmp_path)
    assert calls[0][0] == "uv"
    assert "git+https://github.com/MolCrafts/molcrafts-ci.git@" + "a" * 40 in calls[0][1][4]
    assert "profile-hook" in calls[0][1]


def test_downloaded_hook_rejects_mutable_ci_ref(tmp_path, monkeypatch) -> None:
    ci = load_ci()
    monkeypatch.setattr(ci, "__file__", str(tmp_path / "download" / "ci.py"))
    monkeypatch.setattr(ci, "scrub_git_env", lambda: None)
    monkeypatch.setenv("CI_REF", "dev")
    with pytest.raises(SystemExit, match="full lowercase commit SHA"):
        ci.ci_root(tmp_path)
