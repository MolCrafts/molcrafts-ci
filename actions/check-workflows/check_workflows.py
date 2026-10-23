#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""The MolCrafts CI scheme, checked against a repository's workflows.

Every `.github/workflows/*.yml` under ROOT (default: the current directory)
is read and every violation printed as `file:line: job: [rule] message`; the
exit status is 1 when there is any. The rules are the binding ones of the CI
scheme (Revisions 2-4), the ones a reviewer cannot be trusted to see:

  context      the first job is `context` and its status check reads
               `<file> / context`: a call of the shared context workflow is
               named `<file>` (GitHub appends the called job, `context`); a
               legacy inline Action job is named `<file> / context`
  needs        every other job reaches `context` through `needs`
  skip-pr      every job that a pull request can run is skipped for an
               in-fork pull request: its own `if` carries
               `needs.context.outputs.skip-pr != 'true'` (or a conjunct that
               implies it: `upstream == 'true'`, `publish == 'true'`, an
               event_name test excluding pull_request), or it needs a job
               that is so skipped and has no always()/cancelled() to run
               anyway
  publish      every job that uploads (an `environment:`, a registry publish,
               a GitHub Release) gates on `needs.context.outputs.publish ==
               'true'` and tests no raw github.event_name / github.ref (in
               its if, environment, env or a step's if/env); in
               nightly.yml on `nightly == 'true'`; stable site/API deployment
               on `deploy == 'true'`
  concurrency  the workflow-level block is exactly the canonical one
  pin          MolCrafts/molcrafts-ci/actions/* uses an immutable SHA (legacy @master is accepted)
  comment      no comment mentions workflow_call unless the workflow has it
  name         every job is named `<file> / <what>`
  files        the workflow files are test.yml (required), release.yml,
               nightly.yml and deploy.yml; a workflow_call-only file is a
               library and exempt
  result       test.yml ends in `result`, named `test / result`: it needs
               every other job, runs `if: always()` and fails unless each
               succeeded or was skipped. It is the one check branch rules
               require (`molci rulesets`)
  release      every upload goes to a target .github/release.toml declares
               (molcrafts_ci/release.py: pypi, npm, crates-io,
               vscode-marketplace, github-release, github-pages,
               cloudflare-pages, and their -nightly twins), one per job, from
               the target's file in the target's environment; every declared
               target is published

Run with `uv run --script check_workflows.py [ROOT]` (PEP 723: uv brings
Python and PyYAML), or through MolCrafts/molcrafts-ci/actions/check-workflows.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CI_CONTEXT = HERE.parent / "ci-context" / "action.yml"


def _load_release():
    """release_contract.py beside this script: the release.toml contract of the
    previous CI scheme, loaded by path (this PEP 723 script brings only PyYAML)."""
    path = HERE / "release_contract.py"
    spec = importlib.util.spec_from_file_location("molcrafts_ci_release", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


release = _load_release()

# The only workflow files a repository has (a workflow_call-only file is a
# library another workflow calls, not a run of its own).
WORKFLOW_FILES = ("test", "release", "nightly", "deploy")

# test.yml's last job: the one status check branch rules require. It runs
# whatever happened before it and fails unless every job succeeded or was
# skipped, so renaming or adding a job never strands a pull request.
RESULT_CHECK = "test / result"
RESULT_IF = "always()"
RESULT_STEPS = [
    {
        "name": "Every job succeeded or was skipped",
        "env": {"RESULTS": "${{ toJSON(needs.*.result) }}"},
        "run": 'echo "$RESULTS" | jq -e \'all(.[]; . == "success" or . == "skipped")\'',
    }
]

# The canonical concurrency block, defined once. A workflow-level
# `concurrency:` cannot read job outputs, so every file inlines it; this is
# what keeps the copies identical. Only a feature ref cancels its superseded
# runs. Pushes to dev, master, and tags do not.
GROUP = "{stem}-${{{{ github.workflow }}}}-${{{{ github.event_name }}}}-${{{{ github.ref }}}}"
CANCEL_IN_PROGRESS = (
    '${{ !contains(fromJSON(\'["refs/heads/dev","refs/heads/master"]\'), '
    "github.ref) && !startsWith(github.ref, 'refs/tags/') }}"
)
# These never cancel: a schedule, a release or a deploy is not superseded.
NEVER_CANCEL = {"context", "nightly", "release", "deploy"}

CONTEXT_USES = "MolCrafts/molcrafts-ci/actions/ci-context@master"
LOCAL_CONTEXT_USES = "./actions/ci-context"  # molcrafts-ci itself
CONTEXT_WORKFLOW = "MolCrafts/molcrafts-ci/.github/workflows/context.yml@master"
LOCAL_CONTEXT_WORKFLOW = "./.github/workflows/context.yml"


def valid_action_ref(ref: str) -> bool:
    return ref == "master" or re.fullmatch(r"[0-9a-f]{40}", ref) is not None


def valid_context_use(use: str, local_ok: bool) -> bool:
    if local_ok and use == LOCAL_CONTEXT_USES:
        return True
    prefix = "MolCrafts/molcrafts-ci/actions/ci-context@"
    return use.startswith(prefix) and valid_action_ref(use.removeprefix(prefix))


SKIP_PR = "needs.context.outputs.skip-pr != 'true'"
PUBLISH = "needs.context.outputs.publish == 'true'"
UPSTREAM = "needs.context.outputs.upstream == 'true'"
NIGHTLY = "needs.context.outputs.nightly == 'true'"
DEPLOY = "needs.context.outputs.deploy == 'true'"
# Conjuncts that already keep a job off an in-fork pull request: skip-pr is
# only ever true on a pull_request event, and outside MolCrafts for every
# same-repository one. (Upstream it is also true for a same-repository pull
# request from dev or master, whose head its push already ran in full; a job
# gated on `upstream` alone runs that pull request again, which repeats work
# but is not a fork run.)
NOT_IN_FORK_PR = (SKIP_PR, UPSTREAM, PUBLISH, NIGHTLY, DEPLOY)
NOT_A_PULL_REQUEST = re.compile(
    r"^github\.event_name (?:!= 'pull_request'|== '(?!pull_request')[a-z_]+')$"
)

# Triggers under which a run can be a pull request: its own, or a caller's.
PR_EVENTS = {"pull_request", "pull_request_target", "workflow_call"}

STATUS_OVERRIDE = re.compile(r"\b(always|cancelled)\s*\(")
RAW_REF_TEST = re.compile(r"\bgithub\.(event_name|ref|ref_name|ref_type)\b")
SHARED_ACTION = re.compile(
    r"uses:\s*[\"']?MolCrafts/molcrafts-ci/(?P<path>actions/[^@\s\"']+)@(?P<ref>[^\s\"'#]+)",
    re.IGNORECASE,
)
COMMENT_WORKFLOW_CALL = re.compile(r"(?:^|\s)#.*\bworkflow_call\b")
JOB_NAME = re.compile(r"^(?P<area>[a-z0-9][a-z0-9-]*) / \S")
CALLER_USES = re.compile(r"^MolCrafts/molcrafts-ci/\.github/workflows/ci\.yml@(?P<ref>\S+)$")

PUBLISH_ACTIONS = ("pypa/gh-action-pypi-publish", "softprops/action-gh-release")
DEPLOY_ACTIONS = ("cloudflare/wrangler-action", "cloudflare/pages-action")
PUBLISH_COMMANDS = (
    (re.compile(r"\bcargo\s+(?:\+\S+\s+)?publish\b"), True),
    (re.compile(r"\b(?:npm|pnpm)\s+publish\b"), True),
    (re.compile(r"\b(?:vsce|ovsx)\s+publish\b"), False),
    (re.compile(r"\bgh\s+release\s+(?:create|upload)\b"), False),
    (re.compile(r"\bdevcontainer\s+build\b.*--push\b"), False),
)
EXPRESSION = re.compile(r"\$\{\{.*?\}\}")


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    job: str | None
    rule: str
    message: str

    def __str__(self) -> str:
        where = f"job {self.job}: " if self.job else ""
        return f"{self.file}:{self.line}: {where}[{self.rule}] {self.message}"


def context_outputs() -> list[str]:
    """The outputs a context job maps: whatever actions/ci-context declares."""
    action = yaml.safe_load(CI_CONTEXT.read_text(encoding="utf-8"))
    return list(action["outputs"])


# --- expressions ---------------------------------------------------------


def _unwrap(expr: str) -> str:
    expr = expr.strip()
    if expr.startswith("${{") and expr.endswith("}}") and expr.count("${{") == 1:
        expr = expr[3:-2].strip()
    return expr


def _normalize(expr: str) -> str:
    """Whitespace collapsed outside string literals; outputs['x'] -> outputs.x."""
    out, i, quoted = [], 0, False
    while i < len(expr):
        c = expr[i]
        if c == "'":
            quoted = not quoted
            out.append(c)
        elif c.isspace() and not quoted:
            if out and out[-1] != " ":
                out.append(" ")
        else:
            out.append(c)
        i += 1
    text = "".join(out).strip()
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return re.sub(r"outputs\['([\w-]+)'\]", r"outputs.\1", text)


def _split_top(expr: str, op: str) -> list[str]:
    parts, depth, quoted, start, i = [], 0, False, 0, 0
    while i < len(expr):
        c = expr[i]
        if c == "'":
            quoted = not quoted
        elif not quoted:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif depth == 0 and expr.startswith(op, i):
                parts.append(expr[start:i])
                start = i + len(op)
                i += len(op)
                continue
        i += 1
    parts.append(expr[start:])
    return [p.strip() for p in parts]


def _wrapped(expr: str) -> bool:
    """`(...)` whose opening parenthesis closes at the very end."""
    if not (expr.startswith("(") and expr.endswith(")")):
        return False
    depth, quoted = 0, False
    for i, c in enumerate(expr):
        if c == "'":
            quoted = not quoted
        elif not quoted and c in "()":
            depth += 1 if c == "(" else -1
            if depth == 0 and i < len(expr) - 1:
                return False
    return True


def conjuncts(condition: object) -> set[str]:
    """The terms an `if:` requires: its top-level `&&` operands, flattened."""
    if condition is None:
        return set()
    out: set[str] = set()
    pending = [_normalize(_unwrap(str(condition)))]
    while pending:
        for part in _split_top(pending.pop(), "&&"):
            if _wrapped(part) and len(_split_top(part[1:-1], "||")) == 1:
                pending.append(part[1:-1].strip())
            else:
                out.add(part)
    return out


def requires(condition: object, gate: str) -> bool:
    return _normalize(gate) in conjuncts(condition)


def excludes_in_fork_pr(condition: object) -> bool:
    """The `if` keeps the job off an in-fork pull request by itself."""
    terms = conjuncts(condition)
    return any(_normalize(g) in terms for g in NOT_IN_FORK_PR) or any(
        NOT_A_PULL_REQUEST.match(term) for term in terms
    )


# --- workflow structure --------------------------------------------------


def triggers(spec: dict) -> set[str]:
    # YAML 1.1 reads the key `on` as the boolean True.
    on = spec.get("on", spec.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(t) for t in on}
    if isinstance(on, dict):
        return {str(t) for t in on}
    return set()


def needs_of(job: dict) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else [str(n) for n in needs]


def job_lines(text: str) -> tuple[dict[str, int], dict[str, int]]:
    """Line numbers of the top-level keys and of each job id."""
    top: dict[str, int] = {}
    jobs: dict[str, int] = {}
    root = yaml.compose(text)
    if not isinstance(root, yaml.MappingNode):
        return top, jobs
    for key, value in root.value:
        top[str(key.value)] = key.start_mark.line + 1
        if key.value == "jobs" and isinstance(value, yaml.MappingNode):
            for job_key, _ in value.value:
                jobs[str(job_key.value)] = job_key.start_mark.line + 1
    return top, jobs


def publish_reasons(job: dict) -> list[str]:
    """Why a job counts as uploading or publishing (empty: it does not)."""
    reasons = []
    if job.get("environment"):
        reasons.append("an environment")
    for step in job.get("steps") or []:
        uses = str(step.get("uses", ""))
        for action in PUBLISH_ACTIONS:
            if uses.startswith(action):
                reasons.append(action)
        if (
            uses.startswith("devcontainers/action@")
            and str((step.get("with") or {}).get("publish-features", "false")).lower() == "true"
        ):
            reasons.append("devcontainers/action publish-features")
        for action in DEPLOY_ACTIONS:
            if uses.startswith(action):
                reasons.append(action)
        run = str(step.get("run", "")).replace("\\\n", " ")
        for line in run.splitlines():
            literal = EXPRESSION.sub("", line)  # a --dry-run inside ${{ }} is conditional
            for pattern, has_dry_run in PUBLISH_COMMANDS:
                match = pattern.search(line)
                if match and not (has_dry_run and "--dry-run" in literal):
                    reasons.append(f"`{match.group(0)}`")
    return reasons


_TARGET_USES = (
    ("pypa/gh-action-pypi-publish", "pypi"),
    ("rust-lang/crates-io-auth-action", "crates-io"),
    ("HaaLeo/publish-vscode-extension", "vscode-marketplace"),
    ("softprops/action-gh-release", "github-release"),
    ("actions/deploy-pages", "github-pages"),
    ("cloudflare/wrangler-action", "cloudflare-pages"),
    ("cloudflare/pages-action", "cloudflare-pages"),
)
_TARGET_RUNS = (
    (re.compile(r"\b(?:npm|pnpm)\s+publish\b"), "npm", True),
    (re.compile(r"\bcargo\s+(?:\+\S+\s+)?publish\b"), "crates-io", True),
    (re.compile(r"\b(?:vsce|ovsx)\s+publish\b"), "vscode-marketplace", False),
    (re.compile(r"\bgh\s+release\s+(?:create|upload)\b"), "github-release", False),
)


def published_targets(job: dict, stem: str) -> set[str]:
    """The release.toml targets a job publishes to (nightly.yml: their twins)."""
    found: set[str] = set()
    for step in job.get("steps") or []:
        uses = str(step.get("uses", ""))
        found |= {t for action, t in _TARGET_USES if uses.startswith(action)}
        run = str(step.get("run", "")).replace("\\\n", " ")
        for line in run.splitlines():
            literal = EXPRESSION.sub("", line)
            for pattern, t, has_dry_run in _TARGET_RUNS:
                if pattern.search(line) and not (has_dry_run and "--dry-run" in literal):
                    found.add(t)
    return {f"{t}{release.NIGHTLY}" for t in found} if stem == "nightly" else found


def environment_name(job: dict) -> str:
    env = job.get("environment")
    return str(env.get("name", "")) if isinstance(env, dict) else str(env or "")


# --- the rules -----------------------------------------------------------


def profile_name(root: Path) -> str:
    path = root / ".github" / "partners.env"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("CI_PROFILE="):
            return line.split("=", 1)[1].strip()
    return ""


def is_thin_caller(jobs: dict) -> bool:
    if not jobs:
        return False
    for job in jobs.values():
        job = job or {}
        if job.get("steps") or not CALLER_USES.match(str(job.get("uses") or "")):
            return False
    return True


def check_caller(path: Path, root: Path, spec: dict, text: str) -> list[Violation]:
    """A workflow that only calls molcrafts-ci's named profile."""
    rel = path.relative_to(root).as_posix()
    stem = path.stem
    _, job_line = job_lines(text)
    jobs: dict = spec.get("jobs") or {}
    want = profile_name(root)
    out: list[Violation] = []

    def report(job: str | None, rule: str, message: str, line: int | None = None) -> None:
        line = line or (job_line.get(job, 1) if job else 1)
        out.append(Violation(rel, line, job, rule, message))

    if spec.get("concurrency"):
        report(None, "concurrency", "a caller leaves concurrency to ci.yml")
    if not want:
        report(None, "profile", "CI_PROFILE is not set in .github/partners.env")
    for job_id, job in jobs.items():
        job = job or {}
        ref = CALLER_USES.match(str(job.get("uses"))).group("ref")
        if ref != "master" and not re.fullmatch(r"[0-9a-f]{40}", ref):
            report(job_id, "pin", f"call ci.yml@master (or a 40-character SHA); got @{ref}")
        chosen = str((job.get("with") or {}).get("profile") or "")
        if want and chosen != want:
            report(job_id, "profile", f"with.profile is {chosen!r}; CI_PROFILE is {want!r}")
        area = str((job.get("with") or {}).get("area") or "")
        if area != stem:
            report(job_id, "profile", f"with.area is {area!r}; this file is {stem}.yml")
    return out


def check_workflow(path: Path, root: Path) -> list[Violation]:
    rel = path.relative_to(root).as_posix()
    stem = path.stem
    text = path.read_text(encoding="utf-8")
    spec = yaml.safe_load(text)
    if not isinstance(spec, dict):
        return [Violation(rel, 1, None, "context", "not a workflow (no mapping at the top)")]
    top_line, job_line = job_lines(text)
    jobs: dict = spec.get("jobs") or {}
    if is_thin_caller(jobs):
        return check_caller(path, root, spec, text)
    events = triggers(spec)
    out: list[Violation] = []

    def report(job: str | None, rule: str, message: str, line: int | None = None) -> None:
        line = line or (job_line.get(job, 1) if job else 1)
        out.append(Violation(rel, line, job, rule, message))

    # context: the first job, named per file, running ci-context.
    ids = list(jobs)
    local_ok = (root / "actions/ci-context/action.yml").is_file()
    if "context" not in jobs:
        report(None, "context", f"no `context` job; start the file with `{stem} / context`")
    else:
        ctx = jobs["context"] or {}
        if ids[0] != "context":
            report("context", "context", f"is not the first job (the first is `{ids[0]}`)")
        shared_use = str(ctx.get("uses", ""))
        shared_prefix = CONTEXT_WORKFLOW.removesuffix("master")
        shared_context = (
            shared_use.startswith(shared_prefix)
            and valid_action_ref(shared_use.removeprefix(shared_prefix))
        ) or (local_ok and ctx.get("uses") == LOCAL_CONTEXT_WORKFLOW)
        steps = [s for s in ctx.get("steps") or [] if s.get("id") == "context"]
        policy_implementation = (
            local_ok
            and stem == "context"
            and steps
            and (steps[0].get("uses") == "$/actions/ci-context")
        )
        # The status check must read `<file> / context`. GitHub names a
        # reusable-workflow call `<caller job name> / <called job name>`, so a
        # call is named by its file alone and the shared workflow's own job is
        # `context`; an inline job carries the whole check name itself.
        if shared_context:
            want_name, check = stem, f" (its check reads `{stem} / context`)"
        elif policy_implementation:
            want_name, check = "context", " (a caller's check reads `<file> / context`)"
        else:
            want_name, check = f"{stem} / context", ""
        if ctx.get("name") != want_name:
            report(
                "context",
                "context",
                f"must be named `{want_name}`{check}, not `{ctx.get('name')}`",
            )
        if (
            not shared_context
            and not policy_implementation
            and (not steps or not valid_context_use(str(steps[0].get("uses")), local_ok))
        ):
            report("context", "context", f"use `{CONTEXT_WORKFLOW}` for the shared context job")
        want = {o: f"${{{{ steps.context.outputs.{o} }}}}" for o in context_outputs()}
        got = {str(k): str(v) for k, v in (ctx.get("outputs") or {}).items()}
        # Existing pinned actions expose the original five outputs. New consumers
        # use the reusable workflow and inherit its complete output contract.
        required = want.keys() - {"nightly", "source-ref", "deploy"}
        for name in sorted(required - got.keys()) if not shared_context else []:
            report("context", "context", f"does not map the output `{name}: {want[name]}`")
        for name in sorted(got.keys() - want.keys()):
            report("context", "context", f"maps `{name}`, which ci-context does not output")
        for name in sorted(want.keys() & got.keys()) if not shared_context else []:
            if stem == "context" and name == "source-ref":
                continue  # The reusable workflow resolves the nightly branch to a commit.
            if _normalize(got[name]) != _normalize(want[name]):
                report("context", "context", f"output `{name}` must be `{want[name]}`")

    # needs: every job reaches context.
    def reaches(job_id: str, seen: frozenset[str] = frozenset()) -> bool:
        if job_id in seen:
            return False
        deps = needs_of(jobs.get(job_id) or {})
        return "context" in deps or any(reaches(d, seen | {job_id}) for d in deps if d in jobs)

    for job_id in ids:
        if job_id != "context" and "context" in jobs and not reaches(job_id):
            report(job_id, "needs", "does not reach `context` through `needs`")

    # skip-pr: transitive skipping, unless always()/cancelled() overrides it.
    if events & PR_EVENTS and "context" in jobs:
        gated: dict[str, bool] = {}

        def is_gated(job_id: str, seen: frozenset[str] = frozenset()) -> bool:
            if job_id in gated:
                return gated[job_id]
            if job_id in seen or job_id not in jobs:
                return False
            job = jobs[job_id] or {}
            cond = job.get("if")
            result = excludes_in_fork_pr(cond) or (
                not STATUS_OVERRIDE.search(str(cond or ""))
                and any(is_gated(d, seen | {job_id}) for d in needs_of(job) if d != "context")
            )
            gated[job_id] = result
            return result

        for job_id in ids:
            if job_id == "context" or is_gated(job_id) or (stem == "test" and job_id == "result"):
                continue  # test / result must run to report what was skipped
            cond = str((jobs[job_id] or {}).get("if") or "")
            if STATUS_OVERRIDE.search(cond):
                why = "its `if` uses always()/cancelled(), so a skipped need does not skip it"
            else:
                why = "no job it needs carries the gate"
            report(job_id, "skip-pr", f"{why}; add `{SKIP_PR}` to its `if`")

    # publish: uploads gate on the publish output, not on raw event/ref tests.
    for job_id in ids:
        job = jobs[job_id] or {}
        reasons = publish_reasons(job)
        if not reasons:
            continue
        what = ", ".join(dict.fromkeys(reasons))
        gate = (
            NIGHTLY
            if stem == "nightly"
            else (
                DEPLOY
                if any(action in what for action in DEPLOY_ACTIONS)
                and not stem.startswith("release")
                else PUBLISH
            )
        )
        if not requires(job.get("if"), gate):
            report(job_id, "publish", f"uploads ({what}); its `if` must require `{gate}`")
        tests = [("if", job.get("if")), ("environment", environment_name(job))]
        tests += [(f"env {k}", v) for k, v in (job.get("env") or {}).items()]
        for i, step in enumerate(job.get("steps") or [], 1):
            label = step.get("name") or step.get("id") or step.get("uses") or f"#{i}"
            tests.append((f"step `{label}` if", step.get("if")))
            tests += [(f"step `{label}` env {k}", v) for k, v in (step.get("env") or {}).items()]
        for where, cond in tests:
            if cond is not None and RAW_REF_TEST.search(str(cond)):
                report(
                    job_id,
                    "publish",
                    f"{where} tests github.event_name/github.ref; use `{gate}` instead",
                )

    if stem == "nightly":
        if spec.get("name") != "nightly" or events - {"schedule", "workflow_dispatch"}:
            report(None, "publish", "nightly must be named nightly and use schedule/dispatch only")
        for job_id, job in jobs.items():
            if job_id == "context":
                continue
            for step in (job or {}).get("steps") or []:
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    config = step.get("with") or {}
                    if not config.get("repository") and config.get("ref") != (
                        "${{ needs.context.outputs.source-ref }}"
                    ):
                        report(job_id, "publish", "nightly checkout must use context's source-ref")

    # result: test.yml ends in the one check branch rules require.
    if stem == "test":
        result = jobs.get("result")
        if result is None:
            report(None, "result", f"no `result` job; end the file with `{RESULT_CHECK}`")
        else:
            result = result or {}
            if ids[-1] != "result":
                report("result", "result", f"is not the last job (the last is `{ids[-1]}`)")
            if result.get("name") != RESULT_CHECK:
                report("result", "result", f"must be named `{RESULT_CHECK}`")
            missing = sorted(set(ids) - {"result"} - set(needs_of(result)))
            if missing:
                report("result", "result", f"must need every other job; missing {missing}")
            if _normalize(_unwrap(str(result.get("if") or ""))) != RESULT_IF:
                report("result", "result", f"must run `if: {RESULT_IF}`")
            if result.get("steps") != RESULT_STEPS:
                report("result", "result", "steps must be the canonical result step")

    # concurrency: the canonical block.
    conc = spec.get("concurrency")
    line = top_line.get("concurrency", 1)
    want_cancel = (
        False
        if stem in NEVER_CANCEL
        or stem.startswith(("release-", "publish-"))
        or stem.endswith("-deploy")
        else CANCEL_IN_PROGRESS
    )
    shown = "false" if want_cancel is False else want_cancel
    if not isinstance(conc, dict):
        report(None, "concurrency", "no workflow-level `concurrency:` block", line)
    else:
        group = GROUP.format(stem=stem)
        if str(conc.get("group", "")).strip() != group:
            report(None, "concurrency", f"group must be `{group}`", line)
        got = conc.get("cancel-in-progress")
        got = got.strip() if isinstance(got, str) else got
        if got != want_cancel and not (want_cancel is False and got == "false"):
            report(None, "concurrency", f"cancel-in-progress must be `{shown}`", line)

    # pin + comment: line by line.
    has_call = "workflow_call" in events
    for n, raw in enumerate(text.splitlines(), 1):
        for m in SHARED_ACTION.finditer(raw):
            if not valid_action_ref(m.group("ref")):
                report(
                    None,
                    "pin",
                    f"{m.group('path')}: requires SHA or master; got @{m.group('ref')}",
                    n,
                )
        if not has_call and COMMENT_WORKFLOW_CALL.search(raw):
            report(
                None, "comment", "a comment mentions workflow_call, which this workflow lacks", n
            )

    # name: `<file> / <what>` (a reusable-workflow call is named by its callee).
    # molci-reusable names jobs from the caller's area, not this file's stem.
    if "molci-reusable" not in text:
        pass
    else:
        return out
    for job_id in ids:
        job = jobs[job_id] or {}
        if "uses" in job or job_id == "context":
            continue  # a call is named by its caller; `context` by the context rule
        name = job.get("name")
        m = JOB_NAME.match(str(name or ""))
        if not name:
            report(job_id, "name", f"has no `name:`; name it `{stem} / <what>`")
        elif not m or m.group("area") != stem:
            report(job_id, "name", f"name `{name}` is not `{stem} / <what>`")
    return out


def check_actions(root: Path) -> list[Violation]:
    """The repository's own composite actions must follow @master too."""
    out = []
    for path in sorted((root / ".github/actions").glob("**/action.y*ml")):
        rel = path.relative_to(root).as_posix()
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in SHARED_ACTION.finditer(raw):
                if not valid_action_ref(m.group("ref")):
                    msg = f"{m.group('path')}: requires SHA or master; got @{m.group('ref')}"
                    out.append(Violation(rel, n, None, "pin", msg))
    return out


def _load(path: Path) -> dict:
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return spec if isinstance(spec, dict) else {}


def check_files(root: Path, workflows: list[Path]) -> list[Violation]:
    """files: test.yml, and only the four kinds of run."""
    out = []
    stems = set()
    for path in workflows:
        rel = path.relative_to(root).as_posix()
        if triggers(_load(path)) == {"workflow_call"}:
            continue  # a library another workflow calls
        stems.add(path.stem)
        if path.stem not in WORKFLOW_FILES:
            allowed = ", ".join(f"{s}.yml" for s in WORKFLOW_FILES)
            out.append(
                Violation(rel, 1, None, "files", f"not a workflow file of the scheme ({allowed})")
            )
    if workflows and "test" not in stems:
        out.append(Violation(".github/workflows", 1, None, "files", "no test.yml"))
    return out


def check_release(root: Path, workflows: list[Path]) -> list[Violation]:
    """release: every upload goes to a declared target, from its file and environment."""
    toml = release.RELEASE_TOML.as_posix()
    out: list[Violation] = []
    try:
        declared = release.read_release(root)
    except ValueError as exc:
        return [Violation(toml, 1, None, "release", str(exc))]
    published: dict[str, list[str]] = {}
    for path in workflows:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        _, job_line = job_lines(text)
        for job_id, job in (_load(path).get("jobs") or {}).items():
            job = job or {}
            names = published_targets(job, path.stem)
            line = job_line.get(job_id, 1)
            if len(names) > 1:
                out.append(
                    Violation(
                        rel,
                        line,
                        job_id,
                        "release",
                        f"publishes {sorted(names)}; one target per job",
                    )
                )
            for name in sorted(names):
                published.setdefault(name, []).append(rel)
                tgt = release.target(name)
                if path.stem != tgt.workflow:
                    out.append(
                        Violation(
                            rel,
                            line,
                            job_id,
                            "release",
                            f"publishes {name}, which belongs in {tgt.workflow_file}",
                        )
                    )
                env = environment_name(job) or None
                if env != tgt.environment:
                    want = (
                        f"environment `{tgt.environment}`" if tgt.environment else "no environment"
                    )
                    out.append(
                        Violation(
                            rel,
                            line,
                            job_id,
                            "release",
                            f"publishes {name}; use {want}, not `{env}`",
                        )
                    )
    names = {d.target.name for d in declared or []}
    if published and declared is None:
        out.append(
            Violation(
                toml, 1, None, "release", f"missing; the workflows publish {sorted(published)}"
            )
        )
    for name in sorted(names - published.keys()):
        out.append(Violation(toml, 1, None, "release", f"declares {name}, which no job publishes"))
    for name in sorted(published.keys() - names) if declared is not None else []:
        files = ", ".join(sorted(set(published[name])))
        out.append(
            Violation(toml, 1, None, "release", f"does not declare {name} ({files} publish it)")
        )
    return out


# The rules that read the repository as a whole, not one workflow alone.
REPOSITORY_RULES = frozenset({"files", "result", "release"})


def pinned_ci_ref(root: Path) -> str:
    path = root / ".github" / "partners.env"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("CI_REF="):
            return line.split("=", 1)[1].strip()
    return ""


def adopted(root: Path) -> bool:
    """The repository rules bind molcrafts-ci and every consumer that pins
    CI_REF to a commit (`partners.py pin-ci` adopts them); a legacy consumer
    following @master keeps the per-workflow rules until it migrates."""
    if (root / "actions/ci-context/action.yml").is_file():
        return True
    return re.fullmatch(r"[0-9a-f]{40}", pinned_ci_ref(root)) is not None


def check(root: Path, *, whole: bool | None = None) -> list[Violation]:
    """Every violation under ``root``. ``whole`` forces the repository rules
    on (True) or off (False, a one-concern fixture); by default they apply
    when the repository has adopted them (`adopted`)."""
    whole = adopted(root) if whole is None else whole
    workflows = sorted((root / ".github/workflows").glob("*.yml"))
    out = [v for path in workflows for v in check_workflow(path, root)]
    out += check_files(root, workflows) + check_release(root, workflows)
    out += check_actions(root)
    return out if whole else [v for v in out if v.rule not in REPOSITORY_RULES]


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    violations = check(root)
    annotate = os.environ.get("GITHUB_ACTIONS") == "true"
    for v in violations:
        print(v)
        if annotate:
            print(
                f"::error file={v.file},line={v.line},title=check-workflows [{v.rule}]::{v.message}"
            )
    count = len(list((root / ".github/workflows").glob("*.yml")))
    if violations:
        print(f"{len(violations)} violation(s) in {count} workflow file(s)")
        return 1
    print(f"{count} workflow file(s) follow the MolCrafts CI scheme")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
