"""A test run's numbers as a short markdown table, for a GitHub step summary.

The numbers come from the same readers `molci snapshot` uses
(`molcrafts_ci.producers`), so what a pull request's summary says and what the
dashboard later shows for the same run cannot disagree.

Reporting only: nothing here compares a number against a threshold, and a
missing or unreadable input is written into the table rather than raised, so a
caller never fails a job over what it measured.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from molcrafts_ci.producers import read_cargo_test, read_coverage_py, read_junit, read_lcov

NOT_MEASURED = "—"


def _read(read: Callable[[Path], dict[str, Any]], path: Path) -> tuple[dict[str, Any] | None, str]:
    """``(reading, problem)``: exactly one of the two is meaningful."""
    if not path.is_file():
        return None, f"`{path}` was not produced"
    try:
        return read(path), ""
    except Exception as exc:  # noqa: BLE001 — reported, never raised
        return None, f"`{path}` is unreadable: {exc}"


def _percent(value: float | None) -> str:
    return NOT_MEASURED if value is None else f"{value:.1f}%"


def render_report(
    *,
    title: str,
    junit: Path | None = None,
    cargo_test: Path | None = None,
    coverage: Path | None = None,
    coverage_format: str = "coverage.py",
) -> str:
    """The markdown block for one test run.

    One row: passed, failed and skipped counts, then line and branch coverage.
    A column whose input was not given reads "—"; an input that was given but
    is missing or unreadable is named under the table, so an absent number is
    never mistaken for a zero.
    """
    tests: dict[str, Any] | None = None
    totals: dict[str, Any] = {}
    problems: list[str] = []
    sources: list[str] = []

    if junit and cargo_test:
        raise ValueError("pass one tests report, not both junit and cargo_test")
    tests_path = junit or cargo_test
    if tests_path:
        tests, problem = _read(read_junit if junit else read_cargo_test, tests_path)
        if problem:
            problems.append(problem)
        else:
            sources.append(f"`{tests_path.name}`")

    if coverage:
        reader = read_lcov if coverage_format == "lcov" else read_coverage_py
        cov, problem = _read(reader, coverage)
        if problem:
            problems.append(problem)
        else:
            totals = cov["totals"]
            sources.append(f"`{coverage.name}` ({coverage_format})")

    def count(key: str) -> str:
        return NOT_MEASURED if tests is None else str(tests[key])

    lines = [
        f"### {title}",
        "",
        "| passed | failed | skipped | line coverage | branch coverage |",
        "| ---: | ---: | ---: | ---: | ---: |",
        f"| {count('passed')} | {count('failed')} | {count('skipped')} "
        f"| {_percent(totals.get('lines'))} | {_percent(totals.get('branches'))} |",
        "",
    ]
    if sources:
        lines += [f"Read from {', '.join(sources)}.", ""]
    lines += [f"- {p}" for p in problems]
    if problems:
        lines.append("")
    return "\n".join(lines)
