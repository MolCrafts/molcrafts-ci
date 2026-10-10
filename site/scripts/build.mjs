#!/usr/bin/env node
// Explicit build inputs; no POSIX-only env assignments or sibling UI sync.
import { createRsbuild, loadConfig } from "@rsbuild/core";
import { rm } from "node:fs/promises";
import path from "node:path";

process.env.PUBLIC_USE_MOCK = "0";
process.env.PUBLIC_DATA_BASE ??= "https://raw.githubusercontent.com/MolCrafts/molcrafts-ci/data";
await rm(path.resolve(import.meta.dirname, "../public/data"), { recursive: true, force: true });
const cwd = path.resolve(import.meta.dirname, "..");
const { content } = await loadConfig({ cwd });
const rsbuild = await createRsbuild({ cwd, rsbuildConfig: content });
await rsbuild.build();
