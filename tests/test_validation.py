"""Real Git/source/cache boundaries, including interruption and concurrent hooks."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from molcrafts_ci import validation as v


@pytest.fixture
def repo(tmp_path):
    for args in (
        ["init", "-q"],
        ["config", "user.name", "test"],
        ["config", "user.email", "test@example.test"],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/partners.env").write_text(
        "CI_PROFILE=rust-python\nCI_REF=" + "a" * 40 + "\n"
    )
    (tmp_path / "core.rs").write_text("core")
    (tmp_path / "python.py").write_text("python")
    (tmp_path / "Cargo.lock").write_text("locked")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def config():
    return dict(
        name="synthetic",
        global_inputs=["Cargo.lock", ".github/*"],
        gates=[
            dict(id="core", stage="pre-push", inputs=["core.rs"], run="printf c >> .git/count"),
            dict(
                id="python",
                stage="pre-push",
                inputs=["python.py"],
                depends_on=["core"],
                run="printf p >> .git/count",
            ),
        ],
    )


def execute(repo, config, full=False):
    runner = v.Runner(repo, config)
    assert runner.execute(runner.select(), full=full) == 0
    return (repo / ".git/count").read_text()


def test_success_reused_and_full_forces_execution(repo, config):
    assert execute(repo, config) == "cp"
    assert execute(repo, config) == "cp"
    assert execute(repo, config, full=True) == "cpcp"


@pytest.mark.parametrize("path", ["core.rs", "Cargo.lock", "unknown.txt", ".github/partners.env"])
def test_shared_unknown_lock_and_pin_changes_invalidate_consumers(repo, config, path):
    execute(repo, config)
    target = repo / path
    target.write_text(
        target.read_text().replace("a" * 40, "b" * 40) if path.endswith(".env") else "changed"
    )
    assert execute(repo, config) == "cpcp"


def test_python_only_preserves_core_success(repo, config):
    execute(repo, config)
    (repo / "python.py").write_text("changed")
    assert execute(repo, config) == "cpp"


def test_partner_source_content_invalidates_native_consumers(repo, config):
    partner = repo / ".git/partner"
    partner.mkdir()
    subprocess.run(["git", "init", "-q", str(partner)], check=True)
    source = partner / "bridge.h"
    source.write_text("layout one")
    config["repositories"] = {"binding": str(partner)}
    config["gates"][0]["repositories"] = ["binding"]
    assert execute(repo, config) == "cp"
    assert execute(repo, config) == "cp"
    source.write_text("layout two")
    assert execute(repo, config) == "cpcp"


def test_partner_source_mutation_never_enters_success_cache(repo, config):
    partner = repo / ".git/partner"
    partner.mkdir()
    subprocess.run(["git", "init", "-q", str(partner)], check=True)
    source = partner / "bridge.h"
    source.write_text("initial")
    config["repositories"] = {"binding": str(partner)}
    config["gates"][0]["repositories"] = ["binding"]
    config["gates"][0]["run"] = f"printf mutated > '{source}'"
    runner = v.Runner(repo, config)
    with pytest.raises(ValueError, match="source changed"):
        runner.execute(runner.select())
    assert not list((repo / ".git/molci/success").glob("*.json"))


def test_artifact_export_keeps_other_products_in_success_receipt(repo, config):
    gate = config["gates"][0]
    gate.update(
        produces=["*.whl", "*.tar.gz"],
        artifact_directory="OUTPUT",
        artifact_environment="TESTED_WHEEL",
        artifact_export="*.whl",
        run='printf wheel > "$OUTPUT/a.whl"; printf sdist > "$OUTPUT/a.tar.gz"',
    )
    config["gates"][1]["run"] = '[ "$(cat "$TESTED_WHEEL")" = wheel ]; printf p >> .git/count'
    assert execute(repo, config) == "p"
    assert execute(repo, config) == "p"
    sdist = next((repo / ".git/molci/artifacts").glob("*/*.tar.gz"))
    sdist.write_text("corrupt")
    assert execute(repo, config) == "p"
    assert sdist.read_text() == "sdist"


def test_missing_workspace_binary_invalidates_the_producer(repo, config):
    config["gates"][0]["workspace_artifacts"] = [".git/built-binary"]
    config["gates"][0]["run"] += "; printf executable > .git/built-binary"
    assert execute(repo, config) == "cp"
    assert execute(repo, config) == "cp"
    (repo / ".git/built-binary").unlink()
    assert execute(repo, config) == "cpc"
    assert (repo / ".git/built-binary").read_text() == "executable"


def test_native_selection_omits_only_explicitly_unsupported_platforms(repo, config, monkeypatch):
    config["gates"][1]["os"] = ["Windows"]
    monkeypatch.setattr(v.platform, "system", lambda: "Darwin")
    runner = v.Runner(repo, config)
    assert [g["id"] for g in runner.select()] == ["core"]
    with pytest.raises(ValueError, match="UNSUPPORTED PLATFORM"):
        runner.select(gate="python")


def test_profile_command_and_target_are_cache_inputs(repo, config):
    execute(repo, config)
    config["gates"][1]["run"] = "printf P >> .git/count"
    assert execute(repo, config) == "cpcP"
    runner = v.Runner(repo, config)
    runner.platform = "Other-Architecture"
    assert runner.execute(runner.select()) == 0
    assert (repo / ".git/count").read_text() == "cpcPcP"


@pytest.mark.parametrize("failure", ["exit 7", "kill -TERM $$"])
def test_failure_or_interruption_never_cached(repo, config, failure):
    config["gates"][0]["run"] += "; " + failure
    for _ in range(2):
        runner = v.Runner(repo, config)
        assert runner.execute(runner.select()) != 0
    assert (repo / ".git/count").read_text() == "cc"
    assert not list((repo / ".git/molci/success").glob("*.json"))


def test_mutating_source_never_cached(repo, config):
    config["gates"][0]["run"] = "printf changed > core.rs"
    runner = v.Runner(repo, config)
    with pytest.raises(ValueError, match="source changed"):
        runner.execute(runner.select())
    assert not list((repo / ".git/molci/success").glob("*.json"))


def test_artifact_corruption_invalidates_producer_and_reuses_only_verified_bytes(repo, config):
    config["gates"][0]["produces"] = ["*.whl"]
    config["gates"][0]["artifact_directory"] = "MOLPY_WHEEL_DIR"
    config["gates"][0]["run"] += '; printf wheel > "$MOLPY_WHEEL_DIR/test.whl"'
    execute(repo, config)
    wheel = next((repo / ".git/molci/artifacts").glob("*/*.whl"))
    wheel.write_text("corrupted")
    assert execute(repo, config) == "cpc"
    assert wheel.read_text() == "wheel"


def test_all_pushed_refs_must_match_verified_snapshot(repo):
    sha = v.git(repo, "rev-parse", "HEAD")
    row = f"refs/heads/dev {sha} refs/heads/dev {'0' * 40}"
    assert v.push_commit(repo, row + "\n" + row.replace("dev", "other")) == sha
    (repo / "core.rs").write_text("changed")
    with pytest.raises(ValueError, match="uncommitted"):
        v.push_commit(repo, row)
    subprocess.run(["git", "commit", "-qam", "next"], cwd=repo, check=True)
    with pytest.raises(ValueError, match="differs from HEAD"):
        v.push_commit(repo, row)
    with pytest.raises(ValueError, match="missing Git push refs"):
        v.push_commit(repo, "")


def test_concurrent_runs_share_one_completed_success(repo, config):
    config["gates"][0]["run"] = "sleep 0.2; printf c >> .git/count"
    script = (
        "import json; from pathlib import Path; from molcrafts_ci.validation import Runner; "
        f"r=Runner(Path({str(repo)!r}),json.loads({json.dumps(config)!r})); "
        "raise SystemExit(r.execute(r.select()))"
    )
    children = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ,
        )
        for _ in range(2)
    ]
    for child in children:
        stdout, stderr = child.communicate(timeout=20)
        assert child.returncode == 0, (stdout, stderr)
    assert (repo / ".git/count").read_text() == "cp"


def test_result_rejects_missing_skipped_failed_and_cancelled_platforms():
    path = Path(__file__).parents[1] / "actions/validation-result/result.py"
    spec = importlib.util.spec_from_file_location("validation_result", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    needs = {
        "context": {"result": "success", "outputs": {"validate": "true", "native": "true"}},
        "platform": {"result": "success"},
        "native": {"result": "success"},
    }
    assert module.check(needs) == []
    for status in ["skipped", "failure", "cancelled", None]:
        needs["platform"]["result"] = status
        assert module.check(needs)
    del needs["platform"]
    assert module.check(needs)


def test_full_failure_revokes_an_existing_success(repo, config):
    config["gates"][0]["run"] = "[ ! -f .git/fail ]"
    execute(repo, config)
    (repo / ".git/fail").touch()
    for full in (True, False):
        runner = v.Runner(repo, config)
        assert runner.execute(runner.select(), full=full) != 0


def test_build_environment_and_ignored_corpus_invalidate(repo, config, monkeypatch):
    config["gates"][0]["extra_inputs"] = ["ignored/**/*"]
    (repo / ".git/info/exclude").write_text("ignored/\n")
    execute(repo, config)
    (repo / "ignored").mkdir()
    (repo / "ignored/fixture").write_text("fixture")
    assert execute(repo, config) == "cpcp"
    monkeypatch.setenv("RUSTFLAGS", "-C opt-level=1")
    assert execute(repo, config) == "cpcpcp"


@pytest.mark.parametrize("status", [0, 23])
def test_hpc_submission_is_not_completed_verification(repo, config, monkeypatch, status):
    launcher = repo / "fake-runner"
    launcher.write_text(f"#!/bin/sh\nexit {status}\n")
    launcher.chmod(0o755)
    monkeypatch.setenv("MOLCRAFTS_HOOK_RUNNER", str(launcher))
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.setattr(v, "profile", lambda root: config)
    code = v.main(["verify", "--root", str(repo)])
    assert code == (2 if status == 0 else status)
    assert not (repo / ".git/count").exists()


def test_hpc_rejects_a_different_source_snapshot(repo, config, monkeypatch):
    monkeypatch.setattr(v, "profile", lambda root: config)
    assert v.main(["verify", "--root", str(repo), "--snapshot", "wrong"]) == 2
    assert not (repo / ".git/count").exists()


@pytest.mark.parametrize("kind", ["cycle", "missing", "duplicate"])
def test_invalid_gate_graph_fails_before_execution(repo, config, monkeypatch, kind):
    import yaml

    directory = repo / "engine/profiles"
    directory.mkdir(parents=True)
    monkeypatch.setattr(v, "implementation", lambda: directory.parent)
    if kind == "cycle":
        config["gates"][0]["depends_on"] = ["python"]
    elif kind == "missing":
        config["gates"][0]["depends_on"] = ["missing"]
    else:
        config["gates"].append(config["gates"][0])
    (directory / "rust-python.yml").write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        v.profile(repo)


def test_commit_checks_do_not_claim_native_verification(repo, config, monkeypatch, capsys):
    config["gates"][0]["stage"] = "pre-commit"
    monkeypatch.setattr(v, "profile", lambda root: config)
    assert v.main(["check", "--root", str(repo)]) == 0
    output = capsys.readouterr().out
    assert "Commit checks: PASS" in output
    assert "Native verification: PASS" not in output


def test_wrong_platform_lane_fails_before_execution(repo, config):
    config["platforms"] = {"windows": {"os": "UnsupportedOS", "gates": ["core"]}}
    with pytest.raises(ValueError, match="UNSUPPORTED PLATFORM"):
        v.Runner(repo, config).select(lane="windows")


def test_user_cargo_configuration_invalidates_success(repo, config, monkeypatch):
    home = repo / ".git/cargo-home"
    home.mkdir()
    monkeypatch.setenv("CARGO_HOME", str(home))
    execute(repo, config)
    (home / "config.toml").write_text('[build]\nrustflags = ["--cfg", "different"]\n')
    assert execute(repo, config) == "cpcp"
