# UI Guidelines — molcrafts-ci

Product-local UI record, maintained by `/mol:ui`. The shared MolCrafts
constitution is **not** restated here; it lives in the `mol` plugin at
`skills/ui/references/visual-language.md`. This file records only what
*this product* decided.

Human prose may be added anywhere outside the managed markers below and
will never be rewritten.

<!-- mol:ui:begin -->

## Surface

| | |
|---|---|
| Frontend root | `site/` |
| Archetype | `workbench` |
| Default theme | light (`.dark` palette wired; header `ThemeToggle`) |
| Token layer | `site/src/styles/tokens.css` + the `@theme inline` block in `site/src/styles/tailwind.css` |
| Last ladder stage applied | `info` on 2026-09-20, after re-applying `skeleton` the same day. Stages 3–7 still hold |

## Accent

```css
--color-accent: #0d7377;   /* hue 191, 59° from --status-running (250) */
```

## Typography

Geist and JetBrains Mono are **bundled**, not fetched: `@fontsource/*`
latin subsets imported from `src/index.tsx`, only the three weights the
constitution uses (400 / 500 / 600) and mono's two. The site is published
to GitHub Pages and should not need a third party to be reachable to
render its own type. Cost: five woff2 files, **142 kB total**. Dropping
back to the system stack is one import block.

## Token layer

`styles/tokens.css` holds the product palette and its aliases;
`styles/tailwind.css` is the only `@theme` that maps them to utilities.
The constitution arrives through `constitution-theme.css` (type, radius,
geometry) and `constitution-base.css` (status roles, motion, the four
washes it ships); neither is edited here — both are synced.

No density layer. `density-site.css` was dropped: it retunes body copy to
15px and controls to 40px for a visitor who arrives once, and this is an
instrument an operator holds open. The constitution's own density applies
— body 13px, controls 32 / 28 / 36px, header 44px, status bar 28px, table
rows ~29px.

One red. `--mc-danger` → `--molci-danger` → `var(--status-failed)`, so the
destructive action and the failed status are the same colour. The product
does not define a red of its own: § 5 fixes the status hues. Near-white on
that red measures 4.52:1 — over AA but without margin. That pairing is the
constitution's own (`--destructive` / `--destructive-foreground`), so it is
not this product's to re-tune, and nothing here uses `variant="destructive"`.
Revisit upstream if a destructive button ever ships.

One elevation. `--shadow-raised` and `--mc-shadow-sm` are gone; only
`--shadow-overlay` remains and only overlays may use it.

Spacing is the 4·8·12·16·24·32 ladder. Two values are named because they
are off it for a stated reason: `--spacing-row-pad` (6px, the
constitution's) and `--spacing-status-dot` (6px — a status dot is a mark,
not an icon, and must not out-weigh the word beside it).

The shell's region sizes (`WorkbenchShell.tsx`) are px props to the
resize primitive, not utilities, and are the only literal lengths outside
the token layer. Stage `skeleton` owns them.

## Layout shell

`components/layout/WorkbenchShell.tsx` is the only shell; every surface
renders into it and no route lays itself out.

```
header band (h-header)
navigator 256px │ work surface                          ← resizable columns
──────────────────────────────────────────────────
dock                                                    ← resizable row
```

Constraints: navigator 180–420px, work surface min 320px, dock 140px–70%.
The dock opens closed, collapsed to its 32px tab strip — logs and problems
are what you go looking for, not what greets you.

**There is no inspector column.** Provenance that changes a reader's next
move lives on the record tab header. The shell is navigator + work + dock.

Every tab renders into `WorkSurface` — one padding, one gap, one
scroller. Switching tabs must not shift the content, and a tab that lays
itself out is how a tab strip starts to feel jumpy.

There is no status bar. Once the counts came off it (they changed no
decision) the only thing left was the product name, which the header
already carries, so a 28px band had nothing to hold. The workbench
archetype's layout has no status bar either. Both groups persist their layout
to `localStorage` under `molci.shell` and `molci.columns`, so widths and
dock height survive a reload. Regions are separated by a 1px border and a
surface step; none of them floats or casts a shadow.

One cross-region channel in `lib/`:

- `ProjectRecordsProvider` — one read of the selected project's indexes and
  recent bodies. Overview, dock and record tabs all consume it, so they
  cannot disagree and do not re-fetch.

Selection of project / tab / generation is **URL state**
(`useUrlState`), not a parallel React context. A dock or overview click
writes `{ tab, snapshot }` and the record tab opens that generation.

## Information design (workbench)

Applied 2026-09-20; inspector retired 2026-09-28. Hierarchy is
**Project → record → snapshot**, standing in for Project → Experiment → Run.

Field homes:

| Fact | Home |
|---|---|
| Project name | Navigator + breadcrumb |
| Record names | The tab strip (the navigator does not repeat them) |
| Per-record verdict, reading, commit, run | Overview `RecordTable` |
| How a reading moved | Overview `RecordTrends` (value + delta + sparkline) |
| This generation's payload | That record's own tab (`PayloadView`) |
| Commit, run, profile, producer of this generation | Record tab header |
| Coverage / tests totals | One `MeasureBand` |
| producer_version, schema_version, path, ref | Nowhere on this site — open the Actions run |
| Publish events, failing records | Dock (`Publish log` / `Problems`) |
| Global counts | Nowhere — they changed no decision |

Verdict rule: only a pass/fail count in the payload is a verdict. Coverage
targets and benchmark thresholds are not in the snapshot schema, so those
records report `ready` ("no verdict") rather than borrowing an invented
threshold. Adding real thresholds is a schema change first, a UI change
second.

## Information contract — where each fact lives

| Surface | Question it answers | Carries |
|---|---|---|
| Project overview, top | What is the state, what do I open next | `MetaStrip` (records, snapshots, last published, profile), `StatusInline` over record verdicts, `RecordTable` with each record's reading, commit and run |
| Project overview, bottom | How did it get here | `RecordTrends` — value, delta, sparkline per record; no status/freshness/headline (those are the table's) |
| Record tab | What does *this* generation say | `HistorySelect` (newest 10) + commit + run + profile + producer, then `PayloadView` |

Two consequences worth stating, because both reverse an earlier decision:

- **The generation table is gone.** History is the overview's job now, read as
  a series; the record tab reaches the recent past through a select. The
  earlier rule ("the table *is* the picker") assumed history and detail shared
  a surface. They no longer do.
- **Commit and run are per record, never project-level.** A project-level
  strip carrying them was deleted in `4fc5fbb` for being a lie — records are
  published by separate CI runs at different commits — and the strip
  reintroduced here carries only what genuinely aggregates.

Detail this site does not render — per-line coverage, logs, the job graph —
is reached through `RunLink`, which resolves `repository` + `workflow_run` to
the GitHub Actions run.

## Product components

Feature code (`plugins/`) composes these and nothing else: no `variant=`,
no `size=`, no `className` doing visual work. What is left there is layout
at the call site, which is composition.

| Component | Wraps | Owns |
|---|---|---|
| `WorkbenchShell` | `resizable` | The frame: regions, sizes, resize, persistence, dock collapse |
| `WorkSurface` | `scroll-area` | The one layout every tab renders into |
| `OperationsDock` | `scroll-area`, `button` | Publish log and problems, in one collapsible region |
| `RecordTrends` | `TrendChart` (`<molplot-chart>`) | History: value + delta + sparkline per record |
| `PayloadView` | the below | What one snapshot says, dispatched on payload shape |
| `CoverageFileTable` | `table` | Per-file coverage, worst first (files with gaps only) |
| `MetricTable` | `<dl>` | The fields of one object: label left, quantity right |
| `MetaStrip` | `<dl>` + border tokens | Operational posture of one object as one band |
| `MeasureBand` | `<dl>` + bar | Several measures of one reading (coverage or tests) |
| `StatusInline` | bar + legend | Child status distribution |
| `StatusMark` | `<span>` | The status dot |
| `TrendChart` | `<molplot-chart>` (molplot) | One series sparkline; tooltip is a VL tip field |
| `BandSkeleton` / `RowsSkeleton` | — | The single loading pattern, built from the real structure rather than a measured height |
| `ProjectList` | buttons | Flat project list, selection only |
| `OverviewPanel` | the above | Project situation and next step |
| `RecordTable` | `table` | Inventory of records with reading, status, commit, run |

### One tab for every record

There is no panel per kind. `makeRecordTab` builds all six (Tests,
Coverage, Benchmark, Regression, MolRec, Conformance) and they answer the
same questions in the same order: which generation am I on
(`HistorySelect`), where did it come from (header), what does it say
(`PayloadView`). Provenance that changes the next move is on that header;
detail beyond it is in the Actions run.

`PayloadView` keys on **payload shape, not kind name**, because the kind
name is only a hint: `molrs` publishes `benchmark` from criterion and
`molpy` publishes it from pytest-benchmark. Readers live in `lib/payload.ts`
and are the single owner of "what shape is this" — `record-summary.ts`
reads through them too, so a row's headline and its tab's view can never
disagree. A kind earns its own `Component` only when its reading genuinely
differs; today none does.

## Base primitives installed

`button`, `tabs`, `table`, `scroll-area`, `empty-state`, `separator`,
`tooltip`, `resizable`, `context-menu`, plus the `content-section` block.
`table` was added for the record, snapshot and file inventories;
`content-section` for section grouping without card chrome. `code` was
vendored for the ingest hint and removed again with it — a primitive stays
only while something needs it. All are
vendored by `site/scripts/sync-ui.mjs` from the sibling `molcrafts-ui`
checkout — edit them there, not here. Call sites override a vendored
class only through `className` (the navigator's surface colour is the one
current case).

## Charts

The overview's primary content is history: one panel per record —
label, current value, signed change, and a line over its published
generations. Small multiples, not one plot: passes, percentages,
nanoseconds and absolute error share no axis, and a dual-axis chart would
invent a relationship the data does not have.

Rules this product follows, from the `dataviz` skill:

- **The chart hue is computed, not borrowed.** The brand accent `#0d7377`
  has chroma 0.083 and *reads gray* as a data mark. `--molci-chart` is the
  nearest step in the same hue (191) that clears the palette checks:
  `#008f8c` light, `#00a9a4` dark. Dark wants a narrower lightness band
  (0.48–0.67) than light (0.43–0.77), which is why the dark brand accent
  `#2dd4bf` (L 0.785) fails too.
- **One series, so no legend** — the panel's label names it. Status colour
  appears only on generations that actually failed; the line never carries
  state.
- **A single data point is a reading, not a chart.** The number is the
  chart, and the panel says "no trend yet" instead of drawing one.
- **A series is one profile.** A record can publish the same commit under
  several profiles (`molrs/benchmark` ships linux-x86_64 and
  macos-aarch64), and laying those along a time axis draws a trend out of
  two machines rather than two moments. `toHistory` filters to the newest
  entry's profile and the panel names it.
- Thin marks, hairline baseline, no gridlines, no dashed rules. Every
  generation is a point; failures and the current point are emphasised.
  Tooltip is a Vega-Lite tip field on `<molplot-chart>`, not a native
  `<title>`. Percentages always keep one decimal place (`formatPercent`).

`HISTORY_DEPTH` is 12: one request per generation per record, so a project
with a long history pays for it.

## Containers, states, motion

**Subtraction after the first look.** Reviewing it running removed more
than the static scans ever did. The navigator's expand-to-records (the tab
strip is already that control), the status bar's counts and then the bar,
an "Untracked records" section listing kinds a project does not publish,
the generation table (history is the overview's job; the record tab uses
a select), and eventually the inspector itself — which restated provenance
the record tab header already needed to carry for a shareable view.

The pattern under all of them: **two controls for one action, or two
homes for one fact.** Neither scan catches it; only using the thing does.

**The row is the target.** Both tables put the pointer handler on the
`<tr>` and keep a real `<button>` in the first cell for the keyboard — an
`onClick` on the row alone is skipped by Tab, and a link a few characters
wide is not what the reader is aiming at. Shipping it the other way round
made every table look dead on first use.

**Selection is URL state.** Opening a record tab or clicking a dock row
writes `{ tab, snapshot }` into the address. There is no parallel
selection context and no side panel that opens as a side effect of a click.

**Containers.** Nothing in the product layer is a bordered box except
controls. `MetaStrip`, `MeasureBand` and their skeleton are bands: a rule
underneath, hairlines between cells, no surface of their own. The de-
templating test is the one applied — a box is kept only when it maps to
something the reader could open, drag or delete on its own, and a band of
facts is not that. Overview history tiles are the same: hover wash, no
border, no surface. The overview's record section carries no count either:
the `StatusInline` above it already states how many records there are.

**States.** One pattern, checked per component rather than per page.
`BandSkeleton` / `RowsSkeleton` are the only loading affordance and are
built from the real structure. A disabled control states its reason —
`HistorySelect` is disabled at one generation and says so.

**Motion.** `constitution-base.css` sets `--default-transition-*` as plain
custom properties, but Tailwind reads its own theme keys — so until stage
`motion` every `transition-*` in the app still eased on Tailwind's curve.
The binding lives in the `@theme` block: 150ms on
`cubic-bezier(0.2, 0, 0, 1)`, and the pending pulse at
`--motion-progress-pulse` (1200ms), which the constitution already shipped
and nothing had used. `prefers-reduced-motion: reduce` removes motion
rather than shortening it. No bounce, spin, gradient, shimmer or staggered
reveal exists in the product layer.

## Permitted variance claimed

Only rows from `visual-language.md` § 8 may appear here.

| Axis | This product | Rationale |
|---|---|---|
| Accent hue | teal 191 | Engineering palette shared with the CI brand; clears the 40° band around `--status-running` |
| Default theme | light | Tables, indexes and logs are read for long stretches |
| Layout topology | navigator + tabbed work surface + dock | Snapshot records are tabs of one project, not routes; no inspector column |
| Panel behavior | fixed and resizable, persisted | Workbench default |

## Ownership boundary — what `sync-ui` overwrites

`npm run build` runs `sync-ui` first, which copies these from the sibling
`molcrafts-ui` checkout and **silently reverts any local edit**:

```
src/components/ui/*.tsx      (button, tabs, table, scroll-area, empty-state,
                              separator, tooltip, resizable, context-menu)
src/components/blocks/content-section.tsx
src/components/layout/ExplorerShell.tsx
src/lib/utils.ts
src/styles/constitution-base.css
src/styles/constitution-theme.css
```

Everything else is this product's, including `styles/tokens.css` and
`styles/tailwind.css`. A defect in a synced file is fixed either in
molcrafts-ui or — when the fix can be expressed as style — in this product's
own stylesheet. It is never fixed in place: the next build undoes it.

This was learned the hard way. The ScrollArea overflow below was first patched
in `components/ui/scroll-area.tsx`, typechecked clean, and was gone by the end
of the same build.

## Known debt

Everything below is blocked on something this session could not reach, or is
a toolchain decision rather than a fix.

| Item | Stage | Severity |
|---|---|---|
| Hover, focus, transitions and the trend charts' geometry have never been looked at. No browser automation is reachable here, so they are covered by types, build and static scan only | — | 🟡 |
| No screenshot baselines on the shell or the product components | — | 🟡 |
| `ScrollArea` renders no horizontal `ScrollBar`, and Radix hides the native one on its viewport. Harmless now that overflow scrolls inside each table's own container — fix belongs in molcrafts-ui | `skeleton` | 🟡 |
| Below ~520px the navigator would have to leave the layout too. There is no other way to reach a project | `skeleton` | 🟡 |

Cleared on 2026-09-20: bundled fonts, the four unused tokens, the dark-theme
toggle, `ruff format` drift, the stale `site/public/data` (fixed at the
source — `prepare-data.mjs` now prunes before staging), and the missing test
runner. The destructive-red contrast was closed as an upstream property, not
a product defect; see the token layer above.

## Tests

`site/tests/` mirrors `site/src/`, run by **`@rstest/core`** — the toolchain
is Rspack-family only, so not vitest. It reuses the same `resolve.alias`
shape as `rsbuild.config.ts`, so `@/` needed no second declaration.

68 tests over the pure layers: the payload readers, the record summaries,
URL state, `openRecord`, and the record → tab resolution. Components are
not rendered here; the shell and the product components are
screenshot-baseline territory, which is still open. The cases worth
keeping are the ones real data caught — a series must stay inside one
profile, a producer that publishes no number must not be charted, and
coverage must not be scored as pass or fail.

<!-- mol:ui:end -->
