"""A named profile is one gate registry, without protocol/generation switches."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from molcrafts_ci.validation import Runner, profile

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("name", ["node", "node-python", "python", "rust-python"])
def test_named_profile_loads_without_schema_switch(tmp_path, name):
    pins = tmp_path / ".github/partners.env"
    pins.parent.mkdir()
    pins.write_text(f"CI_PROFILE={name}\nCI_REF=" + "a" * 40 + "\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    loaded = profile(tmp_path)
    runner = Runner(tmp_path, loaded)
    selected = runner.select()
    assert selected
    order = [g["id"] for g in selected]
    for gate in selected:
        for dependency in gate.get("depends_on", []):
            assert order.index(dependency) < order.index(gate["id"])
    assert all(g["stage"] in ("pre-commit", "pre-push") for g in selected)


def test_native_profile_preserves_all_gate_requirements(tmp_path):
    pins = tmp_path / ".github/partners.env"
    pins.parent.mkdir()
    pins.write_text("CI_PROFILE=rust-python\nCI_REF=" + "a" * 40 + "\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    runner = Runner(tmp_path, profile(tmp_path))
    ids = {g["id"] for g in runner.select()}
    assert {
        "fmt",
        "ruff",
        "partners",
        "clippy",
        "doc",
        "test",
        "ffi",
        "cxx",
        "capi",
        "python",
        "types",
        "wasm",
        "mrec",
        "docs",
    } <= ids
    assert {"measure-rust", "measure-conformance"}.isdisjoint(ids)
    assert [g["id"] for g in runner.select(lane="native")] == [g["id"] for g in runner.select()]
