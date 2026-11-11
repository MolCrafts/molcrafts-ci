"""Fail-closed aggregation for schema-2 test.yml. No checkout of PR code needed."""

from __future__ import annotations

import json
import os
import sys


def check(needs: dict) -> list[str]:
    failures = []
    context = needs.get("context", {})
    outputs = context.get("outputs", {})
    if context.get("result") != "success" or outputs.get("validate") != "true":
        failures.append("context must succeed and explicitly require verification")
    if set(needs) != {"context", "platform", "native"}:
        failures.append("expected exactly context, platform and native jobs")
    if needs.get("platform", {}).get("result") != "success":
        failures.append("required platform matrix must explicitly succeed")
    required_native = outputs.get("native")
    if required_native not in ("true", "false"):
        failures.append("context did not specify native applicability")
    expected = "success" if required_native == "true" else "skipped"
    if needs.get("native", {}).get("result") != expected:
        failures.append(f"native result must be {expected}")
    return failures


if __name__ == "__main__":
    failures = check(json.loads(os.environ["NEEDS"]))
    for failure in failures:
        print(f"::error::{failure}")
    sys.exit(bool(failures))
