from __future__ import annotations

import json

import pytest

from molcrafts_ci.producers import (
    MAX_UNCOVERED_PER_FILE,
    github_source,
    read_coverage_py,
    read_junit,
    read_lcov,
)


class TestTestsFromJunit:
    def test_counts_a_single_suite(self, tmp_path) -> None:
        path = tmp_path / "junit.xml"
        path.write_text(
            '<testsuite tests="10" failures="2" errors="1" skipped="3"/>',
            encoding="utf-8",
        )
        assert read_junit(path) == {"passed": 4, "failed": 3, "skipped": 3}

    def test_sums_nested_suites(self, tmp_path) -> None:
        """cargo-nextest wraps its suites in <testsuites>; pytest does not."""
        path = tmp_path / "junit.xml"
        path.write_text(
            "<testsuites>"
            '<testsuite tests="5" failures="1" errors="0" skipped="0"/>'
            '<testsuite tests="3" failures="0" errors="0" skipped="1"/>'
            "</testsuites>",
            encoding="utf-8",
        )
        assert read_junit(path) == {"passed": 6, "failed": 1, "skipped": 1}

    def test_tolerates_missing_attributes(self, tmp_path) -> None:
        path = tmp_path / "junit.xml"
        path.write_text('<testsuite tests="4"/>', encoding="utf-8")
        assert read_junit(path) == {"passed": 4, "failed": 0, "skipped": 0}


class TestCoverageFromCoveragePy:
    def test_reads_totals_and_files(self, tmp_path) -> None:
        path = tmp_path / "coverage.json"
        path.write_text(
            json.dumps(
                {
                    "totals": {
                        "percent_covered": 82.345,
                        "num_branches": 10,
                        "covered_branches": 7,
                    },
                    "files": {
                        "pkg/b.py": {"summary": {"percent_covered": 50.0}, "missing_lines": [3]},
                        "pkg/a.py": {"summary": {"percent_covered": 90.0}, "missing_lines": []},
                    },
                }
            ),
            encoding="utf-8",
        )
        out = read_coverage_py(path)

        assert out["totals"] == {"lines": 82.3, "branches": 70.0}
        assert [f["path"] for f in out["files"]] == ["pkg/a.py", "pkg/b.py"]

    def test_omits_branches_when_not_measured(self, tmp_path) -> None:
        """Without --cov-branch there are no branches; reporting 0% would be a lie."""
        path = tmp_path / "coverage.json"
        path.write_text(
            json.dumps({"totals": {"percent_covered": 50.0, "num_branches": 0}, "files": {}}),
            encoding="utf-8",
        )
        assert read_coverage_py(path)["totals"] == {"lines": 50.0}


LCOV = """SF:src/a.rs
FNF:2
FNH:1
DA:1,1
DA:2,0
DA:3,0
LF:3
LH:1
BRF:4
BRH:2
end_of_record
SF:src/b.rs
FNF:2
FNH:2
DA:1,1
LF:1
LH:1
BRF:0
BRH:0
end_of_record
"""


class TestCoverageFromLcov:
    def test_sums_totals_across_files(self, tmp_path) -> None:
        path = tmp_path / "lcov.info"
        path.write_text(LCOV, encoding="utf-8")
        out = read_lcov(path)

        # lines 2/4, branches 2/4, functions 3/4
        assert out["totals"] == {"lines": 50.0, "branches": 50.0, "functions": 75.0}

    def test_collects_uncovered_lines_per_file(self, tmp_path) -> None:
        path = tmp_path / "lcov.info"
        path.write_text(LCOV, encoding="utf-8")
        files = {f["path"]: f for f in read_lcov(path)["files"]}

        assert files["src/a.rs"]["uncovered"] == [2, 3]
        assert files["src/a.rs"]["lines"] == pytest.approx(33.3)
        assert files["src/b.rs"]["uncovered"] == []

    def test_caps_uncovered_lines(self, tmp_path) -> None:
        """A file with thousands of uncovered lines must not bloat every snapshot."""
        count = MAX_UNCOVERED_PER_FILE + 50
        body = "\n".join(f"DA:{n},0" for n in range(1, count + 1))
        path = tmp_path / "lcov.info"
        path.write_text(f"SF:src/big.rs\n{body}\nLF:{count}\nLH:0\nend_of_record\n", "utf-8")

        assert len(read_lcov(path)["files"][0]["uncovered"]) == MAX_UNCOVERED_PER_FILE


class TestGithubSource:
    def test_refuses_a_tracked_snapshot_without_a_commit(self, monkeypatch) -> None:
        monkeypatch.delenv("GITHUB_SHA", raising=False)
        with pytest.raises(ValueError, match="GITHUB_SHA"):
            github_source(require_commit=True)

    def test_reads_the_actions_environment(self, monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_SHA", "abc123")
        monkeypatch.setenv("GITHUB_REPOSITORY", "MolCrafts/molrs")
        monkeypatch.setenv("GITHUB_RUN_ID", "42")
        source = github_source(require_commit=True)

        assert source.repository == "MolCrafts/molrs"
        assert source.commit == "abc123"
        assert source.workflow_run == 42
