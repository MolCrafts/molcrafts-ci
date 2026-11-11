"""Accept only successful upstream master-push test runs for the release SHA."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


def eligible(run: dict, repository: str, commit: str) -> bool:
    return (
        repository == "MolCrafts/molpy"
        and run.get("head_sha") == commit
        and run.get("head_branch") == "master"
        and run.get("event") == "push"
        and run.get("path") == ".github/workflows/test.yml"
        and (run.get("repository") or {}).get("full_name") == repository
        and (run.get("head_repository") or {}).get("full_name") == repository
    )


def api(path: str) -> list[dict]:
    result = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    if os.environ.get("PUBLISH") != "true":
        print("Dry run: publication disabled; no remote release attestation issued")
        return 0
    repo, sha = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    deadline = time.monotonic() + 90 * 60
    while True:
        runs = [
            run
            for page in api(
                f"repos/{repo}/actions/workflows/test.yml/runs?head_sha={sha}&event=push&per_page=100"
            )
            for run in page["workflow_runs"]
            if eligible(run, repo, sha)
        ]
        latest = max(runs, key=lambda run: (run["id"], run.get("run_attempt", 1)), default=None)
        if latest and latest["status"] == "completed":
            if latest["conclusion"] != "success":
                raise ValueError(
                    f"release commit {sha}: latest upstream master verification failed"
                )
            path = (
                f"repos/{repo}/actions/runs/{latest['id']}/attempts/"
                f"{latest.get('run_attempt', 1)}/jobs?per_page=100"
            )
            jobs = [job for page in api(path) for job in page["jobs"]]
            result = [j for j in jobs if j["name"] == "test / result"]
            native = [j for j in jobs if j["name"] == "test / native"]
            platform = [j for j in jobs if j["name"].startswith("test / platform (")]
            registry = yaml.safe_load(
                (Path(__file__).parents[2] / "profiles/rust-python.yml").read_text("utf-8")
            )
            expected = {
                f"test / platform ({lane})"
                for lane in registry["platforms"]
                if lane not in ("native", "linux")
            }
            if (
                len(result) != 1
                or len(native) != 1
                or {j["name"] for j in platform} != expected
                or any(j.get("conclusion") != "success" for j in result + native + platform)
            ):
                raise ValueError(
                    "release requires successful result, native and all platform jobs "
                    "from the same run"
                )
            print(
                f"Verified {sha}: upstream master run {latest['id']} "
                f"attempt {latest.get('run_attempt', 1)}"
            )
            return 0
        if time.monotonic() >= deadline:
            raise ValueError(
                f"release commit {sha}: no complete successful upstream master verification"
            )
        print(f"Waiting for exact upstream master commit {sha}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(f"::error::{exc}")
