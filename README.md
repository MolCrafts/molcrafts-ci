# molcrafts-ci

Shared GitHub-native engineering infrastructure for MolCrafts:
collect, validate, track, publish, and present developer-facing CI data.

**GitHub:** `MolCrafts/molcrafts-ci`

**Domain peers:**
- [`molcrafts-bench`](https://github.com/MolCrafts/molcrafts-bench)
- [`molcrafts-molrec`](https://github.com/MolCrafts/molcrafts-molrec)

These are standalone developer-facing repositories (MolCrafts is not a monorepo).

## Install (Python)

```bash
pip install molcrafts-ci
# or editable:
pip install -e ".[dev]"
```

Downstream code should use the short import:

```python
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
mci.ingest_snapshot(Path("data"), "molpy", snap)
```

(`molcrafts_ci` remains the canonical package path; `molci` is the public alias.)

## CLI

```bash
molci validate-snapshot path/to/snapshot.json
molci ingest path/to/snapshot.json --project molpy --data-root data
```

## Submitting data from another repository

A producer repository (`molpy`, `molrs`, `molcrafts-molrec`, …) writes a
Snapshot JSON during its own CI and hands it to one Action. That Action
validates it, ingests it into this repository's `data/`, and pushes — and that
push is what makes Cloudflare Pages rebuild the site. There is nothing to
trigger afterwards.

```yaml
# .github/workflows/bench.yml, in the producer repository
permissions:
  contents: read

jobs:
  bench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest --benchmark-json=raw.json          # your producer
      - run: python tools/to_snapshot.py raw.json out/ # your adapter

      - uses: MolCrafts/molcrafts-ci/actions/submit@master
        with:
          snapshot-path: out/*.json
          project: molpy
          app-id: ${{ vars.MOLCRAFTS_APP_ID }}
          private-key: ${{ secrets.MOLCRAFTS_APP_PRIVATE_KEY }}
```

`snapshot-path` takes a path, a glob, or a newline-separated list, so one run
can submit its benchmark, coverage and test records together. Pin `@master` to a
release tag once one exists.

### This repository is its own first producer

`molcrafts-ci` publishes its own `tests` and `coverage` records through the same
Action, in `.github/workflows/ci.yml`:

```yaml
- uses: ./actions/submit
  with:
    snapshot-path: .ci-out/snapshots/*.json
    project: molcrafts-ci
    token: ${{ github.token }}   # same repository — see below
```

So the publish path runs on every push to master, not only when a downstream
repository adopts it. `scripts/ci_snapshot.py` is the producer: it reads
pytest's JUnit XML and coverage.py's JSON and owns those payload shapes —
`molcrafts_ci` never interprets a payload.

Two things make the self-hosted case different from a downstream one:

- **`GITHUB_TOKEN` is enough**, because the push goes to the repository the
  workflow already runs in. No App and no PAT are involved.
- **There is no ingest loop.** GitHub does not start a workflow from a push made
  with `GITHUB_TOKEN`, so the ingest commit cannot trigger another CI run that
  would ingest again. Cloudflare Pages builds from its own webhook, which is not
  subject to that rule, so the site still redeploys.

A pull request builds the same two snapshots with `tracking.enabled` false, so
they are validated and uploaded as an artifact but never published. Only the
Python suite is published; the `site` job's tests are not.

The measuring steps run even when a gate above them failed — a run whose tests
went red is exactly the run whose `tests` record is worth keeping.

### What decides whether anything is published

`manifest.tracking.enabled`, in the snapshot itself — not an Action input:

| `tracking.enabled` | What `submit` does |
| --- | --- |
| `false` | validates, uploads the workflow artifact, pushes nothing |
| `true` | also ingests into `data/` and pushes, which deploys the site |

So a pull-request run and a merge run can use the identical step; only the
snapshot the producer wrote differs.

### Credentials

Pushing into this repository is a cross-repository write, and a workflow's
`GITHUB_TOKEN` is scoped to the repository it runs in — it cannot do this. Use
one of:

- **a MolCrafts GitHub App** (preferred, per the specification): pass `app-id`
  and `private-key`; the Action mints a token that expires with the run. Grant
  the installation `contents: write` on `molcrafts-ci` only.
- **a fine-grained PAT** with `contents: write` on `molcrafts-ci`, passed as
  `token:`.

The Action fails with an explicit message when a tracked snapshot arrives
without a credential, rather than going green having published nothing.

The Actions it calls run on Node 24, so a **self-hosted** runner must be at
least Actions Runner 2.327.1; GitHub-hosted runners already are. Behind an HTTP
proxy, `create-github-app-token` v3 needs `NODE_USE_ENV_PROXY=1` on the step.

If the index branch is protected, the App or PAT identity needs to be allowed to
bypass the rule — otherwise every ingest is rejected five times and the
producer's job fails.

### Re-runs, retries and two producers at once

The ingest is idempotent. A snapshot id is derived from its source, the stored
file is immutable, and an index entry is appended only when that id is not
already indexed, so:

- re-running a job that already published is a no-op — it pushes nothing;
- if another repository pushes first, `submit` re-runs the ingest on the updated
  branch and pushes again (up to five attempts), so neither side's data is lost.

### Other inputs

| Input | Default | Purpose |
| --- | --- | --- |
| `index-repository` | `MolCrafts/molcrafts-ci` | where `data/` lives |
| `index-branch` | the default branch | branch to ingest into |
| `data-root` | `data` | data root inside that repository |
| `artifact-name` | `molcrafts-ci-snapshot` | uploaded artifact name |
| `upload-artifact` | `true` | upload the snapshots as a run artifact |
| `dry-run` | `false` | validate and ingest into a scratch clone, never push |

Outputs: `count`, `tracked`, `ingested`, `skipped`, `pushed`, `commit`. The run
also gets a job summary naming every snapshot and the commit it landed in.

### Ingesting by hand

No Action required — the CLI is the same code path:

```bash
molci ingest path/to/snapshot.json --project molpy --data-root data --if-exists skip
git add data && git commit -m "ingest: molpy" && git push
```

## Frontend (`site/`)

Built with **molcrafts-ui** (shadcn registry copy-in). Dev mocks use
**`rspack-plugin-mock`** (Rsbuild-native) — not hand-served static files.

```bash
# regenerate fixtures via molci, then install + run
python3 -m pip install -e ".[dev]"
npm --prefix site run seed:mock   # or: python3 scripts/seed_mock_data.py
cd site && npm install && npm run dev
```

- `npm run dev` — intercepts `/data/**` with `site/mock/*.mock.ts`
- `npm run seed:mock` — `import molci as mci` ingest → `data/` + refreshes `site/mock/fixtures.ts`
- `npm run dev:data` — skip mock plugin; serve real `public/data` from prepare-data

Register an extra tab without editing the shell:

```ts
import { registerPlugin } from "@/plugins/registry";

registerPlugin({
  id: "api",
  label: "API",
  order: 60,
  available: (ctx) => ctx.records.includes("api"),
  Component: ({ project }) => <div>{project.id}</div>,
});
```

Import the module from `src/index.tsx` (side-effect registration).

UI sources are synced from the sibling `molcrafts-ui` checkout via `npm run sync-ui`.

## Publish package

```bash
pip install build twine
python -m build
# twine upload dist/*   # when ready for PyPI
```

## Specification

See [docs/specification.md](docs/specification.md).
