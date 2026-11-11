# Local-first validation

MolCrafts CI owns the `rust-python` and `cpp-python` gate registries and checks.
Consumers supply their source tree, `.github/partners.env`, one
`.pre-commit-config.yaml` and platform/release workflows. There are no
consumer-side launchers or CI shell scripts.

The C++/Python profile serves Atomiverse. It calls Atomiverse's existing public
configuration and wheel-command APIs, builds one wheel per project and verifies
the pinned MolPy source used by both Rust/CXX and Python. Dependency repositories
are content-hashed and must remain unchanged throughout verification. CMake test
binaries and build caches are checked alongside wheel artifacts, so a deleted
build tree invalidates its producer. CPU model/instruction flags are part of the
compiler-cache identity for `-march=native`. Windows verifies the supported pure
Python delivery; CUDA stays an explicit aarch64 GH200 gate, never an untrusted
self-hosted PR job. Atomiverse owns integration verification in PRs and master
pushes, avoiding a second matrix after a dev merge. Scientific campaigns remain
independent of ordinary verification and keep build attestations and failures.
Content-addressed ccache objects are stored separately from dependency/build
snapshots, so updating a CI pin can retain unchanged C++ compilation outputs.
Atomiverse's development mirror is not in the upstream GitHub fork network;
its upstream PRs all receive independent native validation.

Pre-commit installs the single remote repository at an immutable commit and
reuses its managed environment. Both hook stages execute the same `molci`
entry point. Install with `molci doctor --install-hooks`; the push transport
preserves all Git refs before pre-commit reads stdin. A pushed source snapshot
must match HEAD and be clean. Distinct source snapshots require separate
clean worktrees/pushes. Doctor checks tools, both hooks, pins, cache and runner.

Commands: `molci check`, `molci verify`, `molci verify --full`, `molci run GATE`
and `molci explain GATE`. Every applicable native gate is required before push.
Only successful results with matching source, dependency artifacts, tools,
platform, environment and configuration are reused. Unknown paths invalidate
all gates. OS locks protect shared build artifacts. Full verification and
GitHub ignore success receipts. One tested wheel supplies typing, conformance,
documentation and package checks. Python dependencies share `molpy/uv.lock`.

`MOLCRAFTS_HOOK_RUNNER` must finish validation synchronously on the exact
submitted snapshot. The execution node resolves the pinned CI implementation,
computes its own environment keys and writes a completed receipt. Submission
alone is not validation. Real Slurm integration must be exercised on the site.

External PRs, Dependabot and master pushes run independent native validation
plus platform lanes. Roy-Kid/molpy:dev PRs authored by Roy-Kid and targeting
upstream dev run every platform lane; the identity comes from GitHub event
metadata. Dev pushes run platform integration. Fork pushes compile nothing. Required jobs must explicitly succeed for `test / result`.
Release evidence must come from the exact upstream master commit and one
successful workflow attempt. Untrusted tests use hosted runners and read-only
permissions. Weekly measurements and explicitly requested package publication
are separate; all artifacts use one immutable source commit.

Publish the CI revision first, then use `molci partners pin-ci SHA` to update
consumer hooks, Actions and the locked CI dependency together. Run full native
verification and negative/cache tests before the normal fork-to-upstream PR.
Keep branch protection on `test / result`. Measure timing and runner minutes
before claiming improvements. Follow the consumer's approval rules for pushes.
