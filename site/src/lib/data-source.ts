/**
 * Where the browser reads published data from.
 *
 * Production points at the `data` branch on raw.githubusercontent, not at
 * anything bundled: the data is written by producers between site builds, so
 * bundling it meant the dashboard showed whatever was true at the last deploy,
 * and every deploy carried the whole history. Read at runtime, a new snapshot
 * appears within the CDN's cache window and the bundle stops growing.
 *
 * The default stays `./data` so the dev mock (which intercepts `/data/*`) and
 * `npm run dev:data` (which serves a local checkout of the branch) both work
 * unchanged.
 */
const BASE = (process.env.PUBLIC_DATA_BASE ?? "./data").replace(/\/+$/, "");

/** Resolve a path relative to the data root, e.g. `index/molpy/tests.jsonl`. */
export function dataUrl(relativePath: string): string {
  return `${BASE}/${relativePath.replace(/^\.?\/+/, "")}`;
}
