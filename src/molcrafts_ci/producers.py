"""Adapters from common test and coverage tools to snapshot payloads.

Every repository in the organisation runs a test suite and measures coverage,
and the answers have the same shape wherever they come from: how many tests
passed, what percentage of the code ran. That shape is engineering
infrastructure, not domain semantics — the frontend already reads it without
being told which record it is looking at — so the adapters live here instead of
being copied into each producer repository, where they would drift apart.

What stays out: anything a domain owns. A benchmark payload is not built here.
"""

from __future__ import annotations

import json
import os
import platform
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from molcrafts_ci.manifest import Source

# A file with thousands of uncovered lines would bloat every snapshot that
# mentions it without telling a reader more than the percentage already does.
MAX_UNCOVERED_PER_FILE = 200


def detect_profile() -> str:
    """Machine identity, so one project's history stays comparable within a runner."""
    machine = {"AMD64": "x86_64", "arm64": "aarch64"}.get(platform.machine(), platform.machine())
    return f"{platform.system().lower()}-{machine}"


def github_source(*, require_commit: bool = False) -> Source:
    """Provenance from the GitHub Actions environment."""
    commit = os.environ.get("GITHUB_SHA")
    if require_commit and not commit:
        raise ValueError(
            "GITHUB_SHA is unset; a tracked snapshot would be published under a "
            "placeholder commit and collide with every other run that did the same"
        )
    run = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    return Source(
        repository=os.environ.get("GITHUB_REPOSITORY", "unknown/unknown"),
        commit=commit or "0" * 40,
        ref=os.environ.get("GITHUB_REF"),
        workflow_run=int(run) if run else None,
        run_attempt=int(attempt) if attempt else None,
        timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def read_junit(path: Path) -> dict[str, Any]:
    """JUnit XML, which pytest and cargo-nextest both emit.

    Named `read_*` rather than `tests_*` so importing it into a test module
    does not make pytest collect it as a test.

    The format reports what went wrong, not what went right, so passed is what
    is left once failures, errors and skips are taken out.
    """
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))

    def total(attr: str) -> int:
        return sum(int(s.get(attr) or 0) for s in suites)

    ran = total("tests")
    failed = total("failures") + total("errors")
    skipped = total("skipped")
    return {"passed": ran - failed - skipped, "failed": failed, "skipped": skipped}


def _percent(hit: float, found: float) -> float | None:
    return round(100.0 * hit / found, 1) if found else None


def read_coverage_py(path: Path) -> dict[str, Any]:
    """coverage.py's JSON report (`--cov-report=json`).

    coverage.py measures statements and branches but not functions, and its
    `percent_covered` is a statement percentage — reporting it again under a
    separate `statements` total would dress one reading up as two.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})

    out: dict[str, Any] = {"totals": {}}
    if "percent_covered" in totals:
        out["totals"]["lines"] = round(totals["percent_covered"], 1)
    branches = _percent(totals.get("covered_branches", 0), totals.get("num_branches", 0))
    if branches is not None:
        out["totals"]["branches"] = branches

    out["files"] = [
        {
            "path": name,
            "lines": round(info.get("summary", {}).get("percent_covered", 0.0), 1),
            "uncovered": info.get("missing_lines", [])[:MAX_UNCOVERED_PER_FILE],
        }
        for name, info in sorted(data.get("files", {}).items())
    ]
    return out


_LCOV_FIELD = re.compile(r"^(SF|DA|LF|LH|BRF|BRH|FNF|FNH):(.*)$")


def read_lcov(path: Path) -> dict[str, Any]:
    """LCOV tracefile, which cargo-llvm-cov, grcov and gcov all emit.

    Totals are summed from the per-file counters rather than read from a
    summary line, because a tracefile has no summary record.
    """
    files: list[dict[str, Any]] = []
    sums = dict.fromkeys(("LF", "LH", "BRF", "BRH", "FNF", "FNH"), 0)
    current: dict[str, Any] | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "end_of_record":
            if current:
                files.append(current)
            current = None
            continue
        match = _LCOV_FIELD.match(line)
        if not match:
            continue
        key, value = match.groups()
        if key == "SF":
            current = {"path": value, "uncovered": [], "_lf": 0, "_lh": 0}
        elif current is None:
            continue
        elif key == "DA":
            number, _, count = value.partition(",")
            if count.split(",")[0] in ("0", "-"):
                current["uncovered"].append(int(number))
        else:
            sums[key] += int(value)
            if key == "LF":
                current["_lf"] = int(value)
            elif key == "LH":
                current["_lh"] = int(value)

    out_totals: dict[str, Any] = {}
    for label, (hit, found) in {
        "lines": ("LH", "LF"),
        "branches": ("BRH", "BRF"),
        "functions": ("FNH", "FNF"),
    }.items():
        value = _percent(sums[hit], sums[found])
        if value is not None:
            out_totals[label] = value

    return {
        "totals": out_totals,
        "files": [
            {
                "path": f["path"],
                "lines": _percent(f["_lh"], f["_lf"]) or 0.0,
                "uncovered": sorted(f["uncovered"])[:MAX_UNCOVERED_PER_FILE],
            }
            for f in sorted(files, key=lambda f: f["path"])
        ],
    }
