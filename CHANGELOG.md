# Changelog

Notable changes per release. Format follows [Keep a Changelog][kac];
versioning is [semantic][semver], with the caveat that while the project is
`0.x` the **minor** is the breaking-change axis.

`manifest.schema_version` is derived from that minor, so the shape of a
snapshot and the release that defines it move together — there is no separate
schema version to keep in step.

[kac]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

## [Unreleased]

`manifest.schema_version` is unchanged: nothing here alters the shape of a
snapshot, so this is a patch, not a minor.

### Added

- **`actions/submit` carries a snapshot all the way to the site.** It resolves
  paths and globs, validates, uploads the run artifact and — for snapshots with
  `tracking.enabled` — ingests into the index repository and pushes, which is
  what triggers the Cloudflare Pages rebuild. Producers call one step and are
  done. A GitHub App (`app-id` + `private-key`) or a fine-grained PAT (`token`)
  supplies the cross-repository credential; the step fails loudly when a tracked
  snapshot arrives without one.
- **`molci ingest --if-exists skip` and `--skip-untracked`**, and multiple paths
  per invocation, so one CI run submits its benchmark, coverage and test records
  together. `validate-snapshot` now reports `tracking`, `profile` and
  `generation`; both commands emit one JSON object per line and report every bad
  file rather than only the first.
- `SnapshotIndex.has()`, and an `if_exists` argument on `write_snapshot` and
  `ingest_snapshot` (keyword-only, defaulting to the previous behaviour).
- A repository invariant rejecting `github.token` inside `actions/**` — the
  token that cannot reach another repository.
- **Self-hosting.** `molcrafts-ci` now publishes its own `tests` and `coverage`
  records through its own `actions/submit`, so every push to master exercises
  the path a downstream repository depends on. `scripts/ci_snapshot.py` reads
  pytest's JUnit XML and coverage.py's JSON; `pytest-cov` joins the dev extra.
  The self-push uses `GITHUB_TOKEN` — the push is to its own repository, and
  because GitHub does not start a workflow from a `GITHUB_TOKEN` push, the
  ingest commit cannot trigger another ingest. Cloudflare Pages is unaffected
  and still redeploys.
- CI now lints `scripts/` alongside `src` and `tests`, matching what the
  pre-commit hooks already covered.

### Changed

- **`molci snapshot`** builds `tests` and `coverage` snapshots from a test run's
  native output, so a producer repository no longer carries its own adapter.
  JUnit XML covers pytest and cargo-nextest; coverage is read from coverage.py
  JSON or an LCOV tracefile (`cargo-llvm-cov`, `grcov`). `scripts/ci_snapshot.py`
  is gone — this repository's own CI uses the command it ships.

  These two payload shapes are infrastructure rather than domain semantics: the
  frontend already reads them without being told which record it is looking at.
  Benchmark payloads remain the domain's.

  Coverage file paths are made relative to `--source-root` (the working
  directory by default). cargo-llvm-cov reports absolute build paths, so an
  unprocessed payload recorded the runner's directory layout and never matched
  the same file measured anywhere else.

  The per-file uncovered-line cap drops from 200 to 50, and a truncated list
  now carries `uncovered_total`. Measured on molrs: 369 files, a median of 22
  uncovered lines each, and the dashboard joins the list into one cell that is
  unreadable long before 200. A partial list that looked complete was the worse
  problem; the size (330 KB to 190 KB per snapshot) was the cheaper one.
- The seeded mock data under `data/` was deleted, and `seed_mock_data.py` now
  writes to a gitignored `.mock-data/` root. Those snapshots carried invented
  commit SHAs (`a1b2c3d4…`), a `ref` of `refs/heads/main` for repositories that
  are on `master`, and made-up run ids, and the published site presented them as
  project history. `site/mock/fixtures.ts` is unchanged, so dev mocking is not
  affected.

- Every referenced Action moved to its current major: `checkout` v4 to v7,
  `setup-python` v5 to v7, `setup-node` v4 to v7, `upload-artifact` v4 to v7,
  `download-artifact` v4 to v8, `create-github-app-token` v2 to v3.
  `pypa/gh-action-pypi-publish` stays on `release/v1`, the moving pin its
  maintainers publish.

  These run on Node 24 and so **require Actions Runner 2.327.1 or later**.
  GitHub-hosted runners qualify; a downstream repository on an older
  self-hosted runner has to update it before calling `actions/submit`. Two
  breaking changes in that range do not reach this repository:
  `download-artifact` v5 changed the output path only for downloads **by id**,
  and `release.yml` downloads by name; `setup-python` v7 dropped the
  `pip-install` input, which nothing here used. `create-github-app-token` v3
  removed custom proxy handling, so a proxied runner now needs
  `NODE_USE_ENV_PROXY=1`.

### Removed

- **`ingest.yml`.** The reusable workflow could not have worked: a called
  workflow runs with the caller's `GITHUB_TOKEN`, and `download-artifact`
  without `run-id` only ever sees artifacts from its own run, so it could not
  reach the producer's. Ingestion now happens in the producer's run. See the
  specification, §22.

### Fixed

- The "Notify ingest" step of `actions/submit` echoed a line and exited 0. Every
  tracked snapshot since the Action shipped was validated, uploaded and then
  silently dropped — with a green check.
- The workflow-branch invariant compared `push.branches` against the *current*
  branch, so every feature branch failed it and could not be committed. It now
  compares against the repository's default branch, which is what the check was
  always about.

### Notes

- Ingestion is idempotent: a snapshot id derives from its source, the stored
  file is immutable, and an index entry is appended only when that id is absent.
  A re-run publishes nothing the second time, and a producer that loses the push
  race re-runs its ingest on the updated branch instead of rebasing an append
  into a conflict.

## [0.1.0] - 2026-09-20

First release. `manifest.schema_version` is `1`.

### Added

- **Snapshot model** — `Manifest`, `Source`, `Tracking`, `Snapshot`,
  `GateResult`, with JSON Schema under `schemas/`.
- **Persistence** — generation-tracked, git-friendly layout:
  `data/snapshots/<project>/<record>/<generation>/<snapshot_id>.json` with an
  append-only index at `data/index/<project>/<record>.jsonl`.
- **CLI** — `molci validate-snapshot`, `molci validate-gate`, `molci ingest`.
  `molcrafts_ci` is the package; `molci` is the short import.
- **Workflows** — `ingest` (artifact to index), `ci`, and this `release`.
  The site is deployed by Cloudflare Pages' own Git integration, not from
  here.
- **Site** — a snapshot browser under `site/`, built on the molcrafts-ui
  registry. One shell for every surface: navigator, work surface, an
  inspector that opens on a selection, and a collapsible operations dock,
  all resizable and persisted. The project overview is one trend chart per
  record; each record tab reads its own payload. Views are addressable
  (`#/molpy/conv?profile=linux-x86_64&snapshot=…`), commits link to GitHub,
  and a profile selector keeps a history series inside one machine.

### Notes

- `PayloadView` dispatches on payload **shape**, not on the record name, so a
  producer this code has not seen still renders. molpy's pytest-benchmark and
  molrs's criterion share one tab.
- No coverage target or benchmark threshold exists in the schema, so those
  records report "no verdict" rather than a pass or fail this code invented.

### Known gaps

- `GateResult` is modelled and validated but nothing produces, ingests or
  displays one — the Gate box in the architecture is not wired end to end.
- No `reconcile` workflow, so a dropped ingest is not detected; ingest does
  not verify an artifact digest. (Unreleased: ingestion moved into the
  producer's run, so there is no asynchronous hand-off left to drop.)
- No screenshot baselines; hover, focus and chart geometry are unverified.

## Releasing

Trusted publishing is configured once on PyPI — Publisher: GitHub, owner
`MolCrafts`, repository `molcrafts-ci`, workflow `release.yml`, environment
`pypi` — after which no token lives in this repository.

```bash
# 1. bump pyproject `version` and add a section above; commit
# 2. tag it — the workflow refuses a tag that disagrees with pyproject
git tag v0.1.0
git push origin main --follow-tags
```

[Unreleased]: https://github.com/MolCrafts/molcrafts-ci/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MolCrafts/molcrafts-ci/releases/tag/v0.1.0
