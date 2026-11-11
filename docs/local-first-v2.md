# Local-first validation, schema 2

`rust-python-v2` is opt-in. The existing YAML profiles and TOML CLI retain
v1 selection. MolPy owns commands in `scripts/check.sh`; this repository owns
the gate graph, tool prerequisites, platform lanes, execution and receipts.

Use `molci check`, `molci verify`, `molci verify --full`, `molci run GATE`,
`molci explain GATE`, and `molci doctor`. In MolPy, prefix these commands with
`scripts/ci-hook.sh` instead of `molci` to resolve `CI_REF` through uv's
persistent Git/tool caches. The exact immutable Git dependency is installed
atomically by uv; there is no per-process Git clone and no floating fallback
for schema 2. `scripts/check.sh verify` delegates to full native verification.

Install hooks with `scripts/ci-hook.sh doctor --install-hooks`. Both stages
read `.pre-commit-config.yaml`. The installed pre-push transport preserves all
Git ref tuples before invoking pre-commit, whose current implementation only
passes the first push tuple to its child hook. It contains no check selection.
Running `pre-commit install` later replaces that transport; doctor detects this
and pre-push refuses to validate without the complete tuples. Multiple refs
pointing at HEAD are supported, including annotated tags and ref deletion.
Different pushed source snapshots require separate clean worktrees/pushes.
Relevant uncommitted/untracked source blocks push; direct verification can
validate working changes while developing.

Every native gate is considered on every push. Relevant content, transitive
gate and artifact identities, effective profile/pin, platform, tools and build
environment form the key. Unknown paths enter every key. Only success creates
an atomic receipt. The Git common directory holds the cache and an OS lock;
all writers to the shared Cargo target, wheel artifacts and Python environment
are serialised. Missing/corrupt artifacts invalidate their producer. `--full`
ignores existing successes. GitHub also forces execution, independently of
local receipts. A local receipt is never a branch-protection attestation.

`MOLCRAFTS_HOOK_RUNNER` must run its argv synchronously against the shared exact
snapshot and preserve the exit code. The orchestrator compares source hashes
on both sides and requires a completed result receipt; a submission-only
wrapper fails. Cache keys are computed on the execution node using its tools
and platform. A real Slurm installation remains an integration test required
at the deployment site.

The reusable context takes `profile: rust-python-v2`. Fork pushes and upstream
feature pushes schedule no compilation. Upstream dev gets platform lanes;
every upstream PR and master push also receives independent native validation.
The native lane covers Linux, so those events omit a second Linux lane. All
other lanes come from this profile. A failed, cancelled, missing or skipped
required job cannot pass `test / result`; a non-applicable fork run does not
emit successful validation. Tests always run on hosted runners without
publication credentials. No assertion made by a PR author replaces validation.

Stable release verification accepts only the exact SHA's latest upstream
master-push `test.yml` run and its successful native, platform and result jobs
from the same attempt. Dispatch is a dry run. Weekly nightly measurements are
separate from explicitly requested package builds/publication. All nightly
jobs use the one immutable source ref, and unchanged published commits are not
published again.

## Migration order

1. Run engine tests, lint, workflow schemas and actionlint. Commit this engine
   to a dedicated branch. Publish that exact immutable revision before updating
   a consumer; never pin a consumer to an unavailable revision.
2. Update MolPy's profile and every shared Action/workflow ref with
   `scripts/partners.py pin-ci SHA`. Install and inspect hooks. Run full native
   validation, negative checks and warm-cache/invalidation measurements.
3. Push the development branch to Roy-Kid/molpy and open the normal PR into
   MolCrafts/molpy:dev. Verify actual hosted jobs and required-check behaviour.
   Keep branch protection on `test / result`; no ruleset change is needed.
4. Merge through dev, then the normal dev-to-master PR. Scheduled workflows
   only take effect from the default branch. Run a manual release dry run;
   exercise platform artifact builds before issuing a release tag.
5. Record measured durations, cache hits and runner minutes. Do not infer
   runner-minute or PR critical-path improvements from reduced YAML job counts.

Remote branch pushes must follow the consuming repository's operator approval
rules. No release tag, registry upload or branch-protection edit is part of
local implementation/testing.
