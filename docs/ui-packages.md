# The dashboard's UI packages

The site uses four MolCrafts UI packages that are not on npm yet. They are
committed as tarballs in `site/vendor/ui/`, with `provenance.json` naming the
`molcrafts-ui` commit they came from and their SHA-256 hashes.
`package.json` installs them as `file:` dependencies, so `npm ci` needs
nothing but this repository.

| Package | Used for |
| --- | --- |
| `@molcrafts/ui` | Controls, layout, compiled CSS |
| `@molcrafts/ui-tokens` | Tailwind tokens for the site's own layout |
| `@molcrafts/ui-vega` | The one Vega runtime |
| `@molcrafts/ui-vega-lite` | Charts from Vega-Lite specs (`TrendChart`) |

What the dashboard means by its data (records, coverage, history, links,
plugins) stays in `site/src`; how things look stays in the packages.

## Updating them

1. In `molcrafts-ui`, at a reviewed commit with a clean tree:
   `pnpm prepare:release`, then
   `node scripts/export-consumer-artifacts.mjs /path/to/molcrafts-ci/site/vendor/ui`.
2. Here: `npm --prefix site install` to refresh the lockfile, then
   `molci check site browser`.

`npm run verify:ui` (part of the `site` check) proves the tarballs match
`provenance.json`, the lockfile and what is installed. Update all four
together. Once the packages are on npm, replace the `file:` dependencies with
versions and delete `site/vendor/ui`.

## Look

Comfortable density: 44px navigation rows, 16px labels. Numbers use tabular
figures; monospace is only for code, paths, timestamps and commits.
