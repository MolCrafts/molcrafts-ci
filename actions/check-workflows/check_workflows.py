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

  context      the first job is `context`, named `<file> / context`, runs
               actions/ci-context and maps exactly its outputs
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
               nightly.yml, whose channel publishes from a branch, on
               `needs.context.outputs.upstream == 'true'`
  concurrency  the workflow-level block is exactly the canonical one
  pin          MolCrafts/molcrafts-ci/actions/* uses an immutable SHA (legacy @master is accepted)
  comment      no comment mentions workflow_call unless the workflow has it
  name         every job is named `<file> / <what>`

Run with `uv run --script check_workflows.py [ROOT]` (PEP 723: uv brings
Python and PyYAML), or through MolCrafts/molcrafts-ci/actions/check-workflows.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CI_CONTEXT = HERE.parent / "ci-context" / "action.yml"

# The canonical concurrency block, defined once. A workflow-level
# `concurrency:` cannot read job outputs, so every file inlines it; this is
# what keeps the copies identical. Only a feature ref (not dev, master, main
# or a tag) cancels its superseded runs.
GROUP = "{stem}-${{{{ github.workflow }}}}-${{{{ github.event_name }}}}-${{{{ github.ref }}}}"
CANCEL_IN_PROGRESS = (
    '${{ !contains(fromJSON(\'["refs/heads/dev","refs/heads/master","refs/heads/main"]\'), '
    "github.ref) && !startsWith(github.ref, 'refs/tags/') }}"
)
# These never cancel: a schedule, a release or a deploy is not superseded.
NEVER_CANCEL = {"nightly", "release", "deploy"}

CONTEXT_USES = "MolCrafts/molcrafts-ci/actions/ci-context@master"
LOCAL_CONTEXT_USES = "./actions/ci-context"  # molcrafts-ci itself


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
# Conjuncts that already keep a job off an in-fork pull request: skip-pr is
# only ever true outside MolCrafts, on a pull_request event.
NOT_IN_FORK_PR = (SKIP_PR, UPSTREAM, PUBLISH)
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

PUBLISH_ACTIONS = ("pypa/gh-action-pypi-publish", "softprops/action-gh-release")
PUBLISH_COMMANDS = (
    (re.compile(r"\bcargo\s+(?:\+\S+\s+)?publish\b"), True),
    (re.compile(r"\b(?:npm|pnpm)\s+publish\b"), True),
    (re.compile(r"\b(?:vsce|ovsx)\s+publish\b"), False),
    (re.compile(r"\bgh\s+release\s+(?:create|upload)\b"), False),
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
        run = str(step.get("run", "")).replace("\\\n", " ")
        for line in run.splitlines():
            literal = EXPRESSION.sub("", line)  # a --dry-run inside ${{ }} is conditional
            for pattern, has_dry_run in PUBLISH_COMMANDS:
                match = pattern.search(line)
                if match and not (has_dry_run and "--dry-run" in literal):
                    reasons.append(f"`{match.group(0)}`")
    return reasons


def environment_name(job: dict) -> str:
    env = job.get("environment")
    return str(env.get("name", "")) if isinstance(env, dict) else str(env or "")


# --- the rules -----------------------------------------------------------


def check_workflow(path: Path, root: Path) -> list[Violation]:
    rel = path.relative_to(root).as_posix()
    stem = path.stem
    text = path.read_text(encoding="utf-8")
    spec = yaml.safe_load(text)
    if not isinstance(spec, dict):
        return [Violation(rel, 1, None, "context", "not a workflow (no mapping at the top)")]
    top_line, job_line = job_lines(text)
    jobs: dict = spec.get("jobs") or {}
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
        if ctx.get("name") != f"{stem} / context":
            report(
                "context", "context", f"must be named `{stem} / context`, not `{ctx.get('name')}`"
            )
        steps = [s for s in ctx.get("steps") or [] if s.get("id") == "context"]
        if not steps or not valid_context_use(str(steps[0].get("uses")), local_ok):
            report("context", "context", f"needs a step `id: context` with `uses: {CONTEXT_USES}`")
        want = {o: f"${{{{ steps.context.outputs.{o} }}}}" for o in context_outputs()}
        got = {str(k): str(v) for k, v in (ctx.get("outputs") or {}).items()}
        for name in sorted(want.keys() - got.keys()):
            report("context", "context", f"does not map the output `{name}: {want[name]}`")
        for name in sorted(got.keys() - want.keys()):
            report("context", "context", f"maps `{name}`, which ci-context does not output")
        for name in sorted(want.keys() & got.keys()):
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
            if job_id == "context" or is_gated(job_id):
                continue
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
        if stem == "nightly":
            if not requires(job.get("if"), UPSTREAM):
                report(job_id, "publish", f"uploads ({what}); its `if` must require `{UPSTREAM}`")
            continue
        if not requires(job.get("if"), PUBLISH):
            report(job_id, "publish", f"uploads ({what}); its `if` must require `{PUBLISH}`")
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
                    f"{where} tests github.event_name/github.ref; use `{PUBLISH}` instead",
                )

    # concurrency: the canonical block.
    conc = spec.get("concurrency")
    line = top_line.get("concurrency", 1)
    want_cancel = False if stem in NEVER_CANCEL else CANCEL_IN_PROGRESS
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
    for job_id in ids:
        job = jobs[job_id] or {}
        if "uses" in job:
            continue
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


def check(root: Path) -> list[Violation]:
    workflows = sorted((root / ".github/workflows").glob("*.yml"))
    out = [v for path in workflows for v in check_workflow(path, root)]
    return out + check_actions(root)


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
