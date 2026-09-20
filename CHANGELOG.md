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
- **Workflows** — `ingest` (artifact to index), `publish` (static site to
  Pages), `ci`, and this `release`.
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
  not verify an artifact digest.
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
