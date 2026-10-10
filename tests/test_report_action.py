"""Exercise the composite action's actual shell body before a push."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / "actions/report/action.yml"


def test_report_action_writes_utf8_output_and_its_own_summary(tmp_path: Path) -> None:
    spec = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    summary, output = tmp_path / "summary", tmp_path / "output"
    env = dict(
        os.environ,
        RUNNER_TEMP=str(tmp_path),
        TEST_PYTHON_PREFIX=sys.prefix,
        GITHUB_ACTION_PATH=str(ACTION.parent),
        GITHUB_STEP_SUMMARY=str(summary),
        GITHUB_OUTPUT=str(output),
        TITLE="fixtures (cargo)",
        JUNIT="",
        CARGO_TEST="tests/fixtures/report/cargo-test.log",
        COVERAGE="tests/fixtures/report/lcov.info",
        COVERAGE_FORMAT="lcov",
        # Simulate a non-UTF8 caller. The action must override it.
        PYTHONUTF8="0",
    )
    body = spec["runs"]["steps"][0]["run"].replace(
        'venv="$RUNNER_TEMP/molcrafts-ci-report/venv"', 'venv="$TEST_PYTHON_PREFIX"'
    )
    proc = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-e",
            "-o",
            "pipefail",
            "-c",
            body,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    row = "| 14 | 1 | 2 | 75.0% | — |"
    assert row in summary.read_text(encoding="utf-8")
    assert row in output.read_text(encoding="utf-8")
    assert b"\r" not in output.read_bytes()
