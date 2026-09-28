#!/usr/bin/env node
/**
 * Stage published index data into site/public/data for rsbuild copy + local
 * `dev:data`. Prefers the `index-listing.json` ingest wrote; regenerates one
 * (with per-project `published` timestamps) when staging a tree that has none.
 */

import { cp, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
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

async function buildListing(indexSrc) {
  const indexes = [];
  const published = {};
  for await (const rel of walkJsonl(indexSrc)) {
    indexes.push(`index/${rel}`);
    const project = rel.split("/")[0];
    if (!project) continue;
    const text = await readFile(path.join(indexSrc, rel), "utf8");
    let latest = published[project];
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const stamp = JSON.parse(trimmed).timestamp;
        if (typeof stamp === "string" && (latest == null || stamp > latest)) {
          latest = stamp;
        }
      } catch {
        /* skip a broken line; ingest would have refused it */
      }
    }
    if (latest != null) published[project] = latest;
  }
  indexes.sort();
  return { indexes, published };
}

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

  const listingSrc = path.join(dataRoot, "index-listing.json");
  const listingDest = path.join(publicData, "index-listing.json");
  try {
    await cp(listingSrc, listingDest);
    console.log("index-listing.json: copied from data root");
  } catch {
    const listing = await buildListing(indexSrc);
    await writeFile(listingDest, `${JSON.stringify(listing, null, 2)}\n`, "utf8");
    console.log(`index-listing.json: ${listing.indexes.length} file(s)`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
