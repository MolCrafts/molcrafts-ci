#!/usr/bin/env node
/**
 * Stage published index data into site/public/data for rsbuild copy + local dev.
 * Builds data/index-listing.json from ../data/index (all .jsonl files).
 */

import { cp, mkdir, readdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataRoot = path.resolve(siteRoot, "../data");
const publicData = path.join(siteRoot, "public/data");

async function* walkJsonl(dir, base = dir) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkJsonl(full, base);
    } else if (entry.isFile() && entry.name.endsWith(".jsonl")) {
      yield path.relative(base, full).split(path.sep).join("/");
    }
  }
}

async function main() {
  // Rebuild from scratch. Copying over a previous run leaves streams that
  // ../data no longer publishes sitting in the output, and they ship: a kind
  // deleted upstream would keep serving its old index to the site.
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

  const listing = [];
  for await (const rel of walkJsonl(indexSrc)) {
    listing.push(`data/index/${rel}`);
  }
  listing.sort();

  const payload = `${JSON.stringify({ indexes: listing }, null, 2)}\n`;
  await writeFile(path.join(publicData, "index-listing.json"), payload, "utf8");
  console.log(`index-listing.json: ${listing.length} file(s)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
