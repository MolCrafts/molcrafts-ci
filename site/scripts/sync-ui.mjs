#!/usr/bin/env node
/**
 * Copy molcrafts-ui registry sources into this site (sibling layout).
 *
 * Usage (from site/):
 *   node scripts/sync-ui.mjs
 *
 * Expects:
 *   molcrafts/
 *     molcrafts-ui/
 *     molcrafts-ci/site/
 *
 * If molcrafts-ui is missing but vendored copies already exist, skips with a
 * warning so CI can build from committed sources.
 */

import { access, copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const molcrafts = path.resolve(siteRoot, "../..");
const uiRoot = path.join(molcrafts, "molcrafts-ui");
const srcUi = path.join(uiRoot, "src/components/ui");
const srcBlocks = path.join(uiRoot, "src/components/blocks");
const srcLib = path.join(uiRoot, "src/lib");
const srcStyles = path.join(uiRoot, "src/styles");

const UI = [
  "button",
  "tabs",
  "table",
  "scroll-area",
  "empty-state",
  "separator",
  "tooltip",
  "resizable",
  "context-menu",
];

/** Blocks copied under src/components/blocks/ with their registry names. */
const BLOCKS = ["content-section"];

async function exists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

async function copy(from, to) {
  await mkdir(path.dirname(to), { recursive: true });
  await copyFile(from, to);
  console.log("  →", path.relative(siteRoot, to));
}

async function main() {
  const destUtils = path.join(siteRoot, "src/lib/utils.ts");
  const hasUi = await exists(path.join(uiRoot, "package.json"));
  const hasVendored = await exists(destUtils);

  if (!hasUi) {
    if (hasVendored) {
      console.warn(
        "molcrafts-ui not found; keeping committed vendored UI under src/.",
      );
      return;
    }
    console.error(
      "molcrafts-ui missing at",
      uiRoot,
      "and no vendored UI present. Clone the sibling and re-run.",
    );
    process.exit(1);
  }

  console.log("syncing from", path.relative(molcrafts, uiRoot));

  const destUi = path.join(siteRoot, "src/components/ui");
  for (const name of UI) {
    await copy(path.join(srcUi, `${name}.tsx`), path.join(destUi, `${name}.tsx`));
  }

  const destBlocks = path.join(siteRoot, "src/components/blocks");
  for (const name of BLOCKS) {
    await copy(path.join(srcBlocks, `${name}.tsx`), path.join(destBlocks, `${name}.tsx`));
  }

  await copy(path.join(srcLib, "utils.ts"), destUtils);

  let explorer = await readFile(path.join(srcBlocks, "explorer-shell.tsx"), "utf8");
  await mkdir(path.join(siteRoot, "src/components/layout"), { recursive: true });
  await writeFile(
    path.join(siteRoot, "src/components/layout/ExplorerShell.tsx"),
    explorer,
    "utf8",
  );
  console.log("  →", "src/components/layout/ExplorerShell.tsx");

  const stylesDir = path.join(siteRoot, "src/styles");
  await copy(
    path.join(srcStyles, "constitution-base.css"),
    path.join(stylesDir, "constitution-base.css"),
  );
  await copy(
    path.join(srcStyles, "constitution-theme.css"),
    path.join(stylesDir, "constitution-theme.css"),
  );

  console.log("done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
