# Dashboard Design integration

The dashboard consumes `@molcrafts/design` controls and compiled CSS. The optional
`@molcrafts/design-vega-lite` adapter compiles official Vega-Lite specs and reuses
`@molcrafts/design-vega`'s single Vega runtime. `@molcrafts/design-tokens` supplies the
public Tailwind integration for this product's layout utilities. React, the build
toolchain and official Fluent icons remain normal dependencies. MolPlot, vega-embed,
direct Vega/Lite engine declarations, copied primitives/styles and source-sync are gone.

CI-specific data interpretation, coverage rules, deep links, plugin registration,
record history, workbench composition and storage keys stay in this product.
NativeSelect preserves mobile picker/type-ahead; ResizablePanelHandle comes from the
public Design API. Complete light/dark teal/slate brand families are in brand.css;
Fluent geometry/fonts/status/neutral roles are inherited from Design. ScrollArea
wide-content behavior is fixed and tested in the library, not an internal DOM override here.
TrendChart maps HistoryPoint to an official spec and accessible summary; lifecycle,
compiler loading, themed marks, responsive rendering and text tooltips belong to Design.

## Before npm publishing

No Design package is published by this change. Four immutable tarballs are committed
in site/vendor/design with provenance.json identifying the exact producer commit,
versions and SHA-256 hashes. They contain Rslib JS/types and compiled CSS plus licensing,
not a separately maintained source implementation. Internal exact versions resolve to
these same files through npm overrides. package-lock.json pins dependency resolutions.

`npm ci` works without the producer repository or its CI artifacts. `npm run
verify:design` verifies archive hashes, package identities/exports, dependency versions
and license entries. Refresh only from a reviewed, tested producer commit with clean
working tree: run its `pnpm prepare:release`, then
`node scripts/export-consumer-artifacts.mjs /path/to/molcrafts-ci/site/vendor/design`.
Update all four together, run npm install to regenerate the lockfile, verify:design,
typecheck, tests, build and test:browser, then review a consumer PR. No build/CI workflow
recursively triggers the other repository. Production does not rely on expiring
Actions artifacts or moving branch imports.

When publication is separately authorized, replace file dependencies/overrides with
explicit released package versions, regenerate the lockfile, remove the local artifacts,
and repeat all consumer checks. Do not preserve both paths or source-sync compatibility.

## Validation

- npm run verify:design / typecheck / test / build.
- npx playwright install --with-deps chromium; npm run test:browser.
- Browser checks use committed mock fixtures and exercise chart rendering, dark theme,
  record/history deep links, native pickers, overflow, accessibility and project switching.
- Python CLI/Actions do not import the site or install UI dependencies. A future Design
  workflow may call pinned CI report/submit Actions independently of dashboard deployment.
- MolPlot/Molab migration and native Web Component chart support are separate follow-ups.

## Typography and density

Comfortable density is the default, including engineering dashboards. Project navigation uses 44px rows and 16px labels. Ordinary values use sans typography with tabular figures. Monospace is reserved for code, paths, timestamps and commit identifiers. Compact layouts require a specific space constraint.
