#!/usr/bin/env node
/**
 * Fetch the published index from the `data` branch into ../data.
 *
 * The data does not live on `master` — see the specification, §18 — so a fresh
 * checkout has nothing for prepare-data to stage. The branch is a tarball away
 * and the repository is public, so this needs no credential and no second
 * clone.
 *
 * Cached on purpose: a checkout that already has ../data is left alone, so a
 * local build (and the pre-commit hook that runs one) does not reach the
 * network on every commit. Set MOLCRAFTS_DATA_REFRESH=1 to force a refresh.
 */

import { spawn } from "node:child_process";
import { mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { Readable } from "node:stream";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataRoot = path.resolve(siteRoot, "../data");

const REPOSITORY = process.env.MOLCRAFTS_DATA_REPOSITORY ?? "MolCrafts/molcrafts-ci";
const BRANCH = process.env.MOLCRAFTS_DATA_BRANCH ?? "data";
const URL = `https://codeload.github.com/${REPOSITORY}/tar.gz/refs/heads/${BRANCH}`;

async function isPopulated(dir) {
  try {
    return (await stat(path.join(dir, "index"))).isDirectory();
  } catch {
    return false;
  }
}

function extract(body) {
  return new Promise((resolve, reject) => {
    // --strip-components=1 drops the `<repo>-<branch>/` wrapper the tarball adds.
    const tar = spawn("tar", ["xz", "--strip-components=1", "-C", dataRoot], {
      stdio: ["pipe", "inherit", "inherit"],
    });
    tar.on("error", reject);
    tar.on("close", (code) =>
      code === 0 ? resolve() : reject(new Error(`tar exited with ${code}`)),
    );
    Readable.fromWeb(body).pipe(tar.stdin);
  });
}

async function main() {
  if (process.env.MOLCRAFTS_DATA_REFRESH !== "1" && (await isPopulated(dataRoot))) {
    console.log(`data/ already present; skipping fetch (MOLCRAFTS_DATA_REFRESH=1 to refresh)`);
    return;
  }

  await mkdir(dataRoot, { recursive: true });
  const response = await fetch(URL);
  if (!response.ok) {
    // An empty dashboard built from a failed download would look like a
    // project that has published nothing, which is a different fact.
    throw new Error(`${URL} responded ${response.status} ${response.statusText}`);
  }
  await extract(response.body);
  console.log(`fetched ${REPOSITORY}@${BRANCH} into ${path.relative(siteRoot, dataRoot)}`);
}

await main();
