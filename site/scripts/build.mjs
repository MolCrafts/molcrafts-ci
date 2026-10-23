#!/usr/bin/env node
// Explicit build inputs; no POSIX-only env assignments or sibling UI sync.
import { createRsbuild, loadConfig } from "@rsbuild/core";
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";

process.env.PUBLIC_USE_MOCK = "0";
process.env.PUBLIC_DATA_BASE ??= "https://raw.githubusercontent.com/MolCrafts/molcrafts-ci/data";
// A production build reads the data branch at runtime and bundles no data.
// Whatever `dev:data` staged in public/data must not ship as a stale copy;
// emptied, not removed, so a `dev:data` server running alongside keeps working.
const publicData = path.resolve(import.meta.dirname, "../public/data");
await rm(publicData, { recursive: true, force: true });
await mkdir(publicData, { recursive: true });
const cwd = path.resolve(import.meta.dirname, "..");
const { content } = await loadConfig({ cwd });
const rsbuild = await createRsbuild({ cwd, rsbuildConfig: content });
await rsbuild.build();
