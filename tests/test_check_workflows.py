"""actions/check-workflows: one good and one bad fixture repository per rule
(tests/fixtures/check-workflows/<rule>/{good,bad}), the expression parsing the
gates rely on, and molcrafts-ci's own workflows as the first customer."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "actions/check-workflows/check_workflows.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures/check-workflows"

_spec = importlib.util.spec_from_file_location("check_workflows", SCRIPT)
cw = importlib.util.module_from_spec(_spec)
sys.modules["check_workflows"] = cw
_spec.loader.exec_module(cw)

RULES = ["context", "needs", "skip-pr", "publish", "concurrency", "pin", "comment", "name"]

# What each bad fixture must report, as (file, job, rule) -- exactly these.
EXPECTED_BAD = {
    "context": {
        ("lint.yml", "context", "context"),  # not first, misnamed, cancel, no publish
        ("test.yml", None, "context"),  # no context job at all
    },
    "needs": {("test.yml", "build", "needs"), ("test.yml", "check", "needs")},
    "skip-pr": {
        ("test.yml", "full", "skip-pr"),  # gated on the tier only
        ("test.yml", "either", "skip-pr"),  # the gate is an || operand
        ("test.yml", "report", "skip-pr"),  # always() runs past a skipped need
        ("test.yml", "summary", "skip-pr"),  # so does !cancelled()
        ("lint.yml", "python", "skip-pr"),  # workflow_call: a caller's PR
    },
    "publish": {
        ("release.yml", "pypi", "publish"),
        ("release.yml", "crate", "publish"),  # --dry-run only inside ${{ }}
        ("release.yml", "npm", "publish"),  # raw github.ref test in a step
        ("release.yml", "github", "publish"),
        ("nightly.yml", "pypi", "publish"),
    },
    "concurrency": {
        ("lint.yml", None, "concurrency"),
        ("release.yml", None, "concurrency"),
        ("docs.yml", None, "concurrency"),
    },
    "pin": {("lint.yml", None, "pin"), ("action.yml", None, "pin")},
    "comment": {("docs.yml", None, "comment")},
    "name": {
        ("release.yml", "guard", "name"),
        ("release.yml", "build", "name"),
        ("release.yml", "test", "name"),
    },
}


def summary(violations: list) -> set[tuple[str, str | None, str]]:
    return {(Path(v.file).name, v.job, v.rule) for v in violations}


def test_every_rule_has_a_good_and_a_bad_fixture() -> None:
    assert sorted(p.name for p in FIXTURES.iterdir()) == sorted(RULES)
    assert set(EXPECTED_BAD) == set(RULES)
    for rule in RULES:
        assert (FIXTURES / rule / "good/.github/workflows").is_dir()
        assert (FIXTURES / rule / "bad/.github/workflows").is_dir()


@pytest.mark.parametrize("rule", RULES)
def test_good_fixture_passes(rule: str) -> None:
    assert [str(v) for v in cw.check(FIXTURES / rule / "good")] == []


@pytest.mark.parametrize("rule", RULES)
def test_bad_fixture_fails_on_its_rule_only(rule: str) -> None:
    violations = cw.check(FIXTURES / rule / "bad")
    assert summary(violations) == EXPECTED_BAD[rule], "\n".join(map(str, violations))


def test_context_job_messages() -> None:
    messages = {v.message for v in cw.check(FIXTURES / "context/bad")}
    assert "is not the first job (the first is `python`)" in messages
    assert "must be named `lint / context`, not `lint / ctx`" in messages
    assert "maps `cancel`, which ci-context does not output" in messages
    assert any("does not map the output `publish:" in m for m in messages)


def test_context_outputs_follow_the_action() -> None:
    action = yaml.safe_load((ROOT / "actions/ci-context/action.yml").read_text(encoding="utf-8"))
    assert cw.context_outputs() == list(action["outputs"])
    assert "publish" in cw.context_outputs() and "cancel" not in cw.context_outputs()


def test_violation_format_names_file_line_job_and_rule() -> None:
    v = cw.check(FIXTURES / "needs/bad")[0]
    assert re.fullmatch(r"\.github/workflows/test\.yml:\d+: job build: \[needs\] .+", str(v))


# --- expressions ---------------------------------------------------------

GATE = cw.SKIP_PR


@pytest.mark.parametrize(
    "condition",
    [
        "needs.context.outputs.skip-pr != 'true'",
        "${{ needs.context.outputs.skip-pr != 'true' }}",
        "needs.context.outputs.tier == 'full' && needs.context.outputs.skip-pr != 'true'",
        "(needs.context.outputs.skip-pr != 'true' && matrix.os == 'linux') && true",
        "${{ !cancelled() &&   needs.context.outputs['skip-pr']  != 'true' }}",
    ],
)
def test_gate_is_required(condition: str) -> None:
    assert cw.requires(condition, GATE)


@pytest.mark.parametrize(
    "condition",
    [
        None,
        "needs.context.outputs.skip-pr == 'false' || always()",
        "needs.context.outputs.skip-pr != 'true' || needs.context.outputs.upstream == 'true'",
        "(needs.context.outputs.skip-pr != 'true' || true) && x",
        "!(needs.context.outputs.skip-pr != 'true')",
        "contains('needs.context.outputs.skip-pr != ''true'' && x', 'y')",
    ],
)
def test_gate_is_not_required(condition: str | None) -> None:
    assert not cw.requires(condition, GATE)


@pytest.mark.parametrize(
    ("condition", "excluded"),
    [
        ("needs.context.outputs.skip-pr != 'true'", True),
        ("needs.context.outputs.upstream == 'true' && vars.X != ''", True),
        ("needs.context.outputs.publish == 'true'", True),
        ("github.event_name != 'pull_request'", True),
        ("github.event_name == 'schedule' && always()", True),
        ("github.event_name == 'pull_request'", False),
        ("needs.context.outputs.upstream != 'true'", False),
        ("github.event_name == 'push' || needs.context.outputs.tier == 'full'", False),
    ],
)
def test_conjuncts_that_keep_a_job_off_an_in_fork_pull_request(
    condition: str, excluded: bool
) -> None:
    assert cw.excludes_in_fork_pr(condition) is excluded


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / ".github/workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return tmp_path


def with_jobs(source: str, jobs: str) -> str:
    """A good fixture's header and context job, followed by `jobs`."""
    text = (FIXTURES / source).read_text(encoding="utf-8")
    head = text.split("\n\n  ", 1)[0]  # up to the end of the context job
    return head + "\n" + jobs


def test_transitive_skip_through_a_chain(tmp_path: Path) -> None:
    root = write(
        tmp_path,
        "test.yml",
        with_jobs(
            "skip-pr/good/.github/workflows/test.yml",
            """
  a:
    name: test / a
    needs: context
    if: needs.context.outputs.skip-pr != 'true'
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
  b:
    name: test / b
    needs: [context, a]
    if: success() && needs.context.outputs.tier == 'full'
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
  c:
    name: test / c
    needs: b
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
  d:
    name: test / d
    needs: c
    if: failure()
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
""",
        ),
    )
    assert [str(v) for v in cw.check(root)] == []


def test_a_need_on_context_alone_does_not_gate(tmp_path: Path) -> None:
    root = write(
        tmp_path,
        "test.yml",
        with_jobs(
            "skip-pr/good/.github/workflows/test.yml",
            """
  a:
    name: test / a
    needs: [context]
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
""",
        ),
    )
    assert summary(cw.check(root)) == {("test.yml", "a", "skip-pr")}


def test_a_workflow_no_pull_request_reaches_needs_no_skip_pr_gate(tmp_path: Path) -> None:
    root = write(
        tmp_path,
        "nightly.yml",
        """name: nightly
on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:
concurrency:
  group: nightly-${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}
  cancel-in-progress: false
jobs:
  context:
    name: nightly / context
    runs-on: ubuntu-latest
    outputs:
      tier: ${{ steps.context.outputs.tier }}
      upstream: ${{ steps.context.outputs.upstream }}
      integration: ${{ steps.context.outputs.integration }}
      skip-pr: ${{ steps.context.outputs.skip-pr }}
      publish: ${{ steps.context.outputs.publish }}
    steps:
      - id: context
        uses: MolCrafts/molcrafts-ci/actions/ci-context@master
  bench:
    name: nightly / bench
    needs: context
    if: needs.context.outputs.upstream == 'true'
    runs-on: ubuntu-latest
    steps: [{run: "true"}]
""",
    )
    assert [str(v) for v in cw.check(root)] == []


@pytest.mark.parametrize(
    ("run", "publishes"),
    [
        ("cargo publish -p molrs", True),
        ("cargo +stable publish", True),
        ("cargo publish --dry-run", False),
        ("cargo publish -p x ${{ inputs.dry && '--dry-run' || '' }}", True),
        ("cargo package && cargo test", False),
        ("npm publish --access public", True),
        ("npm publish --dry-run", False),
        ("pnpm publish", True),
        ("npx @vscode/vsce publish -p $VSCE_PAT", True),
        ("npx ovsx publish x.vsix", True),
        ("vsce package", False),
        ('gh release create "$TAG" --generate-notes', True),
        ('gh release upload "$TAG" dist/*', True),
        ('gh release view "$TAG"', False),
        ("echo publish", False),
    ],
)
def test_publish_commands(run: str, publishes: bool) -> None:
    assert bool(cw.publish_reasons({"steps": [{"run": run}]})) is publishes


def test_raw_tests_in_a_publishing_jobs_env(tmp_path: Path) -> None:
    text = (FIXTURES / "publish/good/.github/workflows/release.yml").read_text(encoding="utf-8")
    text = text.replace(
        "    environment:\n      name: pypi\n",
        "    env:\n"
        "      PUBLISH: ${{ github.event_name == 'push' }}\n"
        "    environment:\n      name: pypi\n",
    )
    text = text.replace(
        "      - run: npx @vscode/vsce publish\n",
        "      - run: npx @vscode/vsce publish\n"
        "        env:\n          TAG: ${{ github.ref_type }}\n",
    )
    violations = cw.check(write(tmp_path, "release.yml", text))
    assert {(v.job, v.message.split(" tests ")[0]) for v in violations} == {
        ("pypi", "env PUBLISH"),
        ("crate", "step `#2` env TAG"),
    }


def test_publish_actions_and_environments() -> None:
    assert cw.publish_reasons({"environment": "crates-io"})
    assert cw.publish_reasons({"environment": {"name": "pypi", "url": "x"}})
    assert cw.publish_reasons({"steps": [{"uses": "pypa/gh-action-pypi-publish@release/v1"}]})
    assert cw.publish_reasons({"steps": [{"uses": "softprops/action-gh-release@v2"}]})
    assert not cw.publish_reasons({"steps": [{"uses": "actions/upload-artifact@v7"}]})


def test_the_canonical_concurrency_block_is_the_one_molcrafts_ci_uses() -> None:
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        conc = yaml.safe_load(path.read_text(encoding="utf-8"))["concurrency"]
        assert conc["group"] == cw.GROUP.format(stem=path.stem)
        want = False if path.stem in cw.NEVER_CANCEL else cw.CANCEL_IN_PROGRESS
        assert conc["cancel-in-progress"] == want


def test_molcrafts_ci_follows_its_own_scheme() -> None:
    assert [str(v) for v in cw.check(ROOT)] == []


def test_local_ci_context_only_where_it_exists(tmp_path: Path) -> None:
    text = (FIXTURES / "context/good/.github/workflows/lint.yml").read_text(encoding="utf-8")
    text = text.replace(cw.CONTEXT_USES, cw.LOCAL_CONTEXT_USES)
    root = write(tmp_path, "lint.yml", text)
    assert summary(cw.check(root)) == {("lint.yml", "context", "context")}
    (tmp_path / "actions/ci-context").mkdir(parents=True)
    (tmp_path / "actions/ci-context/action.yml").write_text("name: x\n", encoding="utf-8")
    assert cw.check(root) == []


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv runs the PEP 723 script")
@pytest.mark.parametrize(("rule", "status"), [("pin", 0), ("comment", 1)])
def test_script_exit_status(rule: str, status: int) -> None:
    fixture = FIXTURES / rule / ("good" if status == 0 else "bad")
    proc = subprocess.run(
        ["uv", "run", "-q", "--no-project", "--script", str(SCRIPT), str(fixture)],
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
    )
    assert proc.returncode == status, proc.stdout + proc.stderr
    if status:
        assert "[comment]" in proc.stdout and "1 violation(s)" in proc.stdout


def test_immutable_shared_action_refs(tmp_path: Path) -> None:
    text = (FIXTURES / "pin/good/.github/workflows/lint.yml").read_text(encoding="utf-8")
    text = text.replace("@master", "@" + "a" * 40)
    assert cw.check(write(tmp_path, "lint.yml", text)) == []
