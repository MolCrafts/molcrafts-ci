# molcrafts-ci

Shared CI for MolCrafts repositories, and the dashboard of their test and
coverage history.

**GitHub:** [`MolCrafts/molcrafts-ci`](https://github.com/MolCrafts/molcrafts-ci) ·
**Domain peers:** [`molcrafts-bench`](https://github.com/MolCrafts/molcrafts-bench),
[`molcrafts-molrec`](https://github.com/MolCrafts/molcrafts-molrec)

| Piece | Role |
| --- | --- |
| `.github/workflows/ci.yml` | The one CI workflow every repository calls |
| `.github/workflows/python-release.yml`, `python-nightly.yml` | Build a Python release or nightly package |
| `molci` (Python package `molcrafts-ci`, `import molci`) | Runs the checks of `.github/ci.toml`; builds, validates and ingests snapshots |
| `actions/submit` | Publishes snapshots to the `data` branch |
| `site/` | The dashboard over the `data` branch (Cloudflare Pages) |

## A repository's CI

A repository describes what it checks in **one file, `.github/ci.toml`**.
The same commands run in its git hooks and in CI; there is no `scripts/`
folder, no commit SHA and nothing to keep in step by hand.

```toml
# .github/ci.toml  (molpy)

[env]
PYTHONWARNDEFAULTENCODING = "1"

[tools]
python = "3.12"
rust = true            # molrs is built from source

# Optional. Without it, dependencies resolve normally (PyPI, crates.io).
[partners]
molrs = "MolCrafts/molrs@dev"

[check.lint]
stage = "pre-commit"
run = ["uvx ruff check src tests", "uvx ty check src/molpy"]

[check.test]
run = "uv run --locked --extra dev pytest tests -n auto"
os = ["linux", "macos", "windows"]

[check.docs]
run = "uv run --locked --extra doc zensical build --strict"
```

Its workflow is one call:

```yaml
# .github/workflows/ci.yml
name: ci

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [dev, master]
  workflow_dispatch:

jobs:
  ci:
    uses: MolCrafts/molcrafts-ci/.github/workflows/ci.yml@master
    secrets: inherit
```

A push shows up on the Actions page, and in a failure email, as one run
named `ci` with one line per check:

```text
ci · fix the parser (dev)
  ci / plan            ✓
  ci / lint            ✓
  ci / test (linux)    ✓
  ci / test (macos)    ✗
  ci / test (windows)  ✓
  ci / docs            ✓
  ci / result          ✗   ← the one check branch rules require
```

The git hooks run the same checks:

```yaml
# .pre-commit-config.yaml
default_install_hook_types: [pre-commit, pre-push]
repos:
  - repo: local
    hooks:
      - id: molci-pre-commit
        name: molci check --stage pre-commit
        entry: uvx --from git+https://github.com/MolCrafts/molcrafts-ci@master molci check --stage pre-commit
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
      - id: molci-pre-push
        name: molci check --stage pre-push
        entry: uvx --from git+https://github.com/MolCrafts/molcrafts-ci@master molci check --stage pre-push
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

### `.github/ci.toml`

| Table / key | Meaning | Default |
| --- | --- | --- |
| `[env]` | Environment for every check | none |
| `[tools] python` | Python for every check; a list adds versions | none |
| `[tools] node` | Node version, or the path of an `.nvmrc` | none |
| `[tools] rust` | Install the `rust-toolchain.toml` of this repository and its partners, and cache cargo | `false` |
| `[partners] <name>` | `"owner/repo@branch"`: checked out as `../<name>` | none |
| `[check.<name>] run` | A command, or a list run in order (bash, from the repository root) | required |
| `stage` | `pre-commit`, `pre-push` or `release` | `pre-push` |
| `os` | Any of `linux`, `macos`, `windows` | `["linux"]` |
| `python`, `node`, `rust` | Override `[tools]` for this check | `[tools]` |
| `junit`, `coverage` | Files the check writes: summarised in the run | none |
| `[dashboard] project` | Publish tests and coverage to the dashboard under this name | none |
| `[dashboard] branch` | Pushes to this branch become dashboard history | `master` |
| `[nightly]` | `package`, `version-file`, `rename`: see python-nightly | none |

A misspelt key is an error that names the file and the key.

### What a run does

The full rules live in `src/molcrafts_ci/plan.py`:

- A push to a **feature branch** of MolCrafts runs the first leg of each
  check (linux, the first Python). Pushes to `dev` and `master`, pull
  requests, forks and manual runs run every leg.
- Each OS runs the first Python of a check; further Pythons run on the first OS only.
- A **pull request inside a fork** runs nothing: the push to the fork
  already ran everything.
- A newer push to the same feature branch cancels the older run.
- Checks with `stage = "release"` run only in `python-release.yml`.

### Partners

A partner is a MolCrafts repository built from source next to this one,
for changes that span both. CI clones it at the named branch into
`../<name>`. Locally, `molci check` uses the sibling checkout you have and
prints its branch and commit, so a difference from CI is visible:

```text
molrs: ../molrs is dev @ 1a2b3c4 (CI uses dev)
```

`molci partners` clones a missing sibling. Remove the `[partners]` entry (and
the matching path source) to build against the published package instead.

### Release

```yaml
# .github/workflows/release.yml
name: release

on:
  push:
    tags: ["v*"]
  workflow_dispatch:   # a dry run: build and check, publish nothing

jobs:
  build:
    uses: MolCrafts/molcrafts-ci/.github/workflows/python-release.yml@master
    permissions:
      contents: read
      actions: read

  pypi:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v') && github.repository_owner == 'MolCrafts'
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v8
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

`python-release.yml` checks the tag is on master, waits for `ci` to have
passed on the tagged commit, runs the `release` checks (against published
dependencies, no partners), builds, and checks the package version is the
tag's. The PyPI upload stays in the caller because PyPI trusts the caller's
workflow file.

`python-nightly.yml` builds `dev` as the `[nightly]` package
(`<version>.dev<YYYYmmddHHMM>`, partner dependencies renamed to their
nightly packages) for a nightly workflow to upload the same way.

### Dashboard

With `[dashboard]`, a push to its branch on MolCrafts turns the junit and
coverage files of the first leg that writes them into `tests` and `coverage`
snapshots and publishes them with `actions/submit`. The repository needs the
`MOLCRAFTS_CI_SSH_KEY` secret: the private half of the deploy key that can
write to `MolCrafts/molcrafts-ci`.

## `molci`

```bash
molci check                     # every check but release ones
molci check lint test           # these checks
molci check --stage pre-commit  # one stage
molci partners                  # clone missing partners into ../
```

Snapshots, for producers that build their own records:

```bash
molci snapshot --out out/ --junit junit.xml --coverage coverage.json --track
molci validate-snapshot out/*.json
molci ingest out/*.json --project molpy --data-root data
molci report --title "test" --junit junit.xml --coverage coverage.json
```

A **snapshot** is a `Manifest` (record, source commit and run, producer,
profile, tracking) plus a payload. This repository owns the `tests` and
`coverage` payloads; a benchmark or domain record is built by its own
producer and only submitted here. `tracking.enabled` decides whether a
snapshot becomes history; `tracking.generation` starts a new history when a
record's shape changes incompatibly (generation 2 of a commit is its own
snapshot, `<record>-<profile>-g2-<commit>`). A stored snapshot is never
rewritten.

```python
from pathlib import Path
import molci as mci

snap = mci.Snapshot(
    manifest=mci.Manifest(
        record="benchmark",
        source=mci.Source(repository="MolCrafts/molpy", commit="abc1234"),
        producer="pytest-benchmark",
        tracking=mci.Tracking(enabled=True, generation=1),
    ),
    payload={"metrics": {"mean_ns": 12.5}},
)
mci.ingest_snapshot(Path("data"), "molpy", snap)  # also refreshes index-listing.json
```

### Submitting from another producer

```yaml
- uses: MolCrafts/molcrafts-ci/actions/submit@master
  with:
    snapshot-path: out/*.json
    project: molpy
    ssh-key: ${{ secrets.MOLCRAFTS_CI_SSH_KEY }}
```

`manifest.tracking.enabled` in each snapshot decides whether it is
published (`true`) or only validated and uploaded as an artifact (`false`).
Snapshots go to the orphan **`data` branch** (`index/`, `snapshots/`,
`index-listing.json`), which the dashboard reads at runtime from
`raw.githubusercontent.com`. The ingest is idempotent: a re-run pushes
nothing, and a push race re-runs the ingest on the moved branch (up to five
attempts). Credentials: a deploy key (`ssh-key`), a GitHub App (`app-id` +
`private-key`), or a fine-grained PAT (`token`).

## Dashboard site (`site/`)

Built with the vendored `@molcrafts/ui` packages under `site/vendor/ui`
(see [docs/ui-packages.md](docs/ui-packages.md)).

```bash
npm --prefix site ci
npm --prefix site run seed:mock   # regenerate mock fixtures through molci
npm --prefix site run dev         # mock data
npm --prefix site run dev:data    # the real data branch, fetched locally
npm --prefix site run build       # production: reads the data branch at runtime
```

The browser: **Navigator** (projects, newest publish first), **Overview**
(facts, verdicts, record table, history), **Record tab** (one generation,
with its commit, run, profile and producer) and **Dock** (publish log and
problems; a row opens that record at that generation). A link is
`#/<project>/<tab>?profile=&snapshot=`. Register another tab with
`registerPlugin` from `@/plugins/registry`.

## Working on molcrafts-ci

```bash
uv sync --locked --extra dev
uvx pre-commit install
uv run --locked --extra dev molci check     # what CI runs
```

molcrafts-ci checks itself with its own `.github/ci.toml` and `ci.yml`.
Inside the shared workflows, `$/actions/...` is the Action from the same
commit as the workflow, so a change is tested by the pull request that makes
it (runner 2.336.0 or newer). Versioning: while `0.x`, the minor is the
breaking-change axis, and `manifest.schema_version` is that minor.
The history is git.

## Previous scheme (until every repository has moved)

Repositories not yet on `.github/ci.toml` still call these at `@master`;
they stay working and are removed when the last caller has moved:
`actions/ci-context`, `actions/check-workflows`, `actions/setup-partners`
(with `src/molcrafts_ci/partners.py` and `.github/partners.env`),
`actions/setup-python`, `actions/setup-node`, `actions/setup-rust`.
`actions/setup-python` is also used by `ci.yml` itself.
