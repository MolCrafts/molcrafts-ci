#!/usr/bin/env node
/**
 * Drop site/public/data before a build that reads data at runtime.
 *
 * rsbuild copies everything under public/ into the bundle. `npm run dev:data`
 * leaves a local checkout of the data branch there, and without this a
 * production build would ship it — and the browser would be served that stale
 * copy from its own origin instead of the live branch, which looks current and
 * is not. The directory is gitignored, so CI never has one; this is for the
 * machine that ran dev:data yesterday.
 */

import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const publicData = path.join(siteRoot, "public/data");

// Emptied, not removed. rsbuild's `output.copy` fails outright on a source
// directory that does not exist, so deleting it broke any `dev:data` server
// running alongside a build. An empty directory copies nothing, which is the
// whole point, and costs nobody a rebuild.
await rm(publicData, { recursive: true, force: true });
await mkdir(publicData, { recursive: true });
