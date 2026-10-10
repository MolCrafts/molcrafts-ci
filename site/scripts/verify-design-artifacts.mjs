import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
const root = new URL("../vendor/design/", import.meta.url);
const lock = JSON.parse(await readFile(new URL("../package-lock.json", import.meta.url), "utf8"));
const metadata = JSON.parse(await readFile(new URL("provenance.json", root), "utf8"));
assert.equal(metadata.repository, "https://github.com/MolCrafts/molcrafts-ui");
assert.match(metadata.commit, /^[a-f0-9]{40}$/);
assert.equal(metadata.mode, "unpublished-fixed-package-artifacts");
const expected = new Set(["@molcrafts/design", "@molcrafts/design-tokens", "@molcrafts/design-vega", "@molcrafts/design-vega-lite"]);
assert.equal(metadata.packages.length, expected.size);
const archives = new Set();
for (const item of metadata.packages) {
  assert.ok(expected.delete(item.name), `Duplicate/unexpected package: ${item.name}`);
  assert.match(item.file, /^molcrafts-design(?:-tokens|-vega|-vega-lite)?-0\.0\.1\.tgz$/);
  archives.add(item.file);
  const file = new URL(item.file, root);
  const bytes = await readFile(file);
  assert.equal(createHash("sha256").update(bytes).digest("hex"), item.sha256);
  const installed = lock.packages[`node_modules/${item.name}`];
  assert.equal(installed.integrity, `sha512-${createHash("sha512").update(bytes).digest("base64")}`, "Lockfile must identify the exact local artifact, not cached same-version bytes");
  const packed = JSON.parse(execFileSync("tar", ["-xOf", file.pathname, "package/package.json"], { encoding: "utf8" }));
  assert.equal(packed.name, item.name); assert.equal(packed.version, item.version); assert.equal(packed.license, "MIT");
  const entries = execFileSync("tar", ["-tzf", file.pathname], { encoding: "utf8" }).trim().split("\n");
  for (const entry of entries) assert.ok(entry.startsWith("package/") && !entry.split("/").includes(".."));
  for (const name of ["LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md"]) assert.ok(entries.includes(`package/${name}`));
  for (const value of Object.values(packed.exports)) for (const path of typeof value === "string" ? [value] : Object.values(value)) {
    assert.ok(entries.includes(`package/${path.slice(2)}`));
    const expected = execFileSync("tar", ["-xOf", file.pathname, `package/${path.slice(2)}`]);
    const actual = await readFile(new URL(`../node_modules/${item.name}/${path.slice(2)}`, import.meta.url));
    assert.deepEqual(actual, expected, "Installed public exports must match the producer artifact");
  }
  for (const [name, version] of Object.entries(packed.dependencies ?? {})) {
    assert.ok(!/^(?:file:|workspace:|link:)/.test(version));
    if (name.startsWith("@molcrafts/")) assert.equal(version, metadata.packages.find(pkg => pkg.name === name)?.version);
  }
}
assert.equal(expected.size, 0);
assert.deepEqual((await readdir(root)).filter(name => name.endsWith(".tgz")).sort(), [...archives].sort());
console.log(`Verified four local Design packages from producer ${metadata.commit}, exports, licenses and SHA-256 hashes.`);
