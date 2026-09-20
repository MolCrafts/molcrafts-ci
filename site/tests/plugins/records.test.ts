import { describe, expect, it } from "@rstest/core";

import { recordMatches, RECORDS } from "@/plugins/records";

/**
 * The rule the registry uses to decide which tab opens an on-disk record: a
 * record tab matches the single record and does NOT match an empty record set —
 * that second half is what separates it from the whole-project overview.
 */
function tabForRecord(record: string) {
  return (
    RECORDS.filter((k) => recordMatches([record], k.aliases) && !recordMatches([], k.aliases)).sort(
      (a, b) => a.order - b.order,
    )[0] ?? null
  );
}

describe("recordMatches", () => {
  it("matches case-insensitively", () => {
    expect(recordMatches(["Tests"], ["tests"])).toBe(true);
    expect(recordMatches(["tests"], ["TESTS"])).toBe(true);
  });

  it("does not match an empty record set", () => {
    // Load-bearing: pluginForRecord relies on this to tell a record tab from
    // the overview, which is available for every project.
    expect(recordMatches([], ["tests", "test"])).toBe(false);
  });

  it("matches any alias", () => {
    expect(recordMatches(["cov"], ["coverage", "cov", "conv"])).toBe(true);
  });
});

describe("tab ids", () => {
  it("are unique", () => {
    const ids = RECORDS.map((k) => k.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("claim no alias twice", () => {
    const seen = new Set<string>();
    for (const k of RECORDS) {
      for (const alias of k.aliases) {
        expect(seen.has(alias)).toBe(false);
        seen.add(alias);
      }
    }
  });
});

describe("record resolution", () => {
  it("routes coverage to the conv tab", () => {
    // `conv` is the short URL for Coverage; the record on disk is `coverage`.
    expect(tabForRecord("coverage")?.id).toBe("conv");
    expect(tabForRecord("cov")?.id).toBe("conv");
  });

  it("routes every record the fixtures publish", () => {
    for (const record of ["tests", "coverage", "benchmark", "regression", "molrec", "conformance"]) {
      expect(tabForRecord(record), record).not.toBeNull();
    }
  });

  it("returns null for a record nothing claims", () => {
    expect(tabForRecord("fuzzing")).toBeNull();
  });
});
