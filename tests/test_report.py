from __future__ import annotations

from pathlib import Path

import pytest

from molcrafts_ci.cli import main
from molcrafts_ci.producers import read_coverage_py, read_junit
from molcrafts_ci.report import render_report

FIXTURES = Path(__file__).parent / "fixtures" / "report"
HEADER = "| passed | failed | skipped | line coverage | branch coverage |"


def _row(markdown: str) -> str:
    """The one data row under the table header."""
    lines = markdown.splitlines()
    return lines[lines.index(HEADER) + 2]


class TestRenderReport:
    def test_junit_and_coverage_py(self) -> None:
        out = render_report(
            title="test / python",
            junit=FIXTURES / "pytest.xml",
            coverage=FIXTURES / "coverage-py.json",
        )
        assert out.startswith("### test / python\n")
        # 20 run, 2 failures + 1 error, 3 skipped; 3/4 statements, 5/8 branches.
        assert _row(out) == "| 14 | 3 | 3 | 75.0% | 62.5% |"
        assert "Read from `pytest.xml`, `coverage-py.json` (coverage.py)." in out

    def test_numbers_are_the_dashboards(self) -> None:
        """The table and `molci snapshot` read the same files the same way."""
        tests = read_junit(FIXTURES / "pytest.xml")
        cov = read_coverage_py(FIXTURES / "coverage-py.json")["totals"]
        out = render_report(
            title="t", junit=FIXTURES / "pytest.xml", coverage=FIXTURES / "coverage-py.json"
        )
        assert _row(out) == (
            f"| {tests['passed']} | {tests['failed']} | {tests['skipped']} "
            f"| {cov['lines']:.1f}% | {cov['branches']:.1f}% |"
        )

    def test_cargo_test_and_lcov(self) -> None:
        out = render_report(
            title="test / rust",
            cargo_test=FIXTURES / "cargo-test.log",
            coverage=FIXTURES / "lcov.info",
            coverage_format="lcov",
        )
        # LCOV here records no branches, so that column is not measured.
        assert _row(out) == "| 14 | 1 | 2 | 75.0% | — |"

    def test_tests_only(self) -> None:
        out = render_report(title="t", cargo_test=FIXTURES / "cargo-test.log")
        assert _row(out) == "| 14 | 1 | 2 | — | — |"
        assert "was not produced" not in out

    def test_missing_input_is_named_not_raised(self, tmp_path: Path) -> None:
        out = render_report(
            title="t",
            junit=tmp_path / "junit.xml",
            coverage=FIXTURES / "coverage-py.json",
        )
        assert _row(out) == "| — | — | — | 75.0% | 62.5% |"
        assert f"- `{tmp_path / 'junit.xml'}` was not produced" in out

    def test_unreadable_input_is_named_not_raised(self, tmp_path: Path) -> None:
        bad = tmp_path / "cargo-test.log"
        bad.write_text("error: could not compile `molrs`\n", encoding="utf-8")
        out = render_report(title="t", cargo_test=bad)
        assert _row(out) == "| — | — | — | — | — |"
        assert "is unreadable: no cargo test summary" in out

    def test_one_tests_report_only(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            render_report(
                title="t",
                junit=FIXTURES / "pytest.xml",
                cargo_test=FIXTURES / "cargo-test.log",
            )


class TestReportCli:
    def test_prints_the_table(self, capsys) -> None:
        argv = ["report", "--title", "test / python", "--junit", str(FIXTURES / "pytest.xml")]
        assert main(argv) == 0
        out = capsys.readouterr().out
        assert out.startswith("### test / python\n")
        assert _row(out) == "| 14 | 3 | 3 | — | — |"

    def test_failed_tests_do_not_fail_the_command(self, capsys) -> None:
        argv = ["report", "--title", "t", "--cargo-test", str(FIXTURES / "cargo-test.log")]
        assert main(argv) == 0
        assert _row(capsys.readouterr().out) == "| 14 | 1 | 2 | — | — |"

    def test_missing_input_does_not_fail_the_command(self, tmp_path: Path, capsys) -> None:
        argv = ["report", "--title", "t", "--junit", str(tmp_path / "absent.xml")]
        assert main(argv) == 0
        assert "was not produced" in capsys.readouterr().out
