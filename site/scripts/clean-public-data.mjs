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

import { rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
await rm(path.join(siteRoot, "public/data"), { recursive: true, force: true });
