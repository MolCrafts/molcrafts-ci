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
        kind="benchmark",
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
  available: (ctx) => ctx.kinds.includes("api"),
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
