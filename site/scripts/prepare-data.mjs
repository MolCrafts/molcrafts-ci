#!/usr/bin/env node
/**
 * Stage published index data into site/public/data for rsbuild copy + local
 * `dev:data`, including the `index-listing.json` that `molci ingest` wrote.
 */

import { cp, mkdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataRoot = path.resolve(siteRoot, "../data");
const publicData = path.join(siteRoot, "public/data");

async function main() {
  // Rebuild from scratch. Copying over a previous run leaves records that
  // ../data no longer publishes sitting in the output, and they ship: a
  // record deleted upstream would keep serving its old index to the site.
  await rm(publicData, { recursive: true, force: true });
  await mkdir(publicData, { recursive: true });

  const indexSrc = path.join(dataRoot, "index");
  const indexDest = path.join(publicData, "index");
  try {
    const st = await stat(indexSrc);
    if (st.isDirectory()) {
      await mkdir(indexDest, { recursive: true });
      await cp(indexSrc, indexDest, { recursive: true });
    }
  } catch {
    await mkdir(indexDest, { recursive: true });
  }

  const snapSrc = path.join(dataRoot, "snapshots");
  const snapDest = path.join(publicData, "snapshots");
  try {
    const st = await stat(snapSrc);
    if (st.isDirectory()) {
      await mkdir(snapDest, { recursive: true });
      await cp(snapSrc, snapDest, { recursive: true });
    }
  } catch {
    /* optional */
  }

  // `molci ingest` writes the listing with every ingest; it is the one source.
  await cp(path.join(dataRoot, "index-listing.json"), path.join(publicData, "index-listing.json"));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
