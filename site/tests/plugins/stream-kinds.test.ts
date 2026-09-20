import { describe, expect, it } from "@rstest/core";

import { kindMatches, STREAM_KINDS } from "@/plugins/stream-kinds";

/**
 * The rule the registry uses to decide which tab opens an on-disk kind: a
 * stream tab matches the single kind and does NOT match an empty kind set —
 * that second half is what separates it from the whole-project overview.
 */
function tabForKind(kind: string) {
  return (
    STREAM_KINDS.filter((k) => kindMatches([kind], k.aliases) && !kindMatches([], k.aliases)).sort(
      (a, b) => a.order - b.order,
    )[0] ?? null
  );
}

describe("kindMatches", () => {
  it("matches case-insensitively", () => {
    expect(kindMatches(["Tests"], ["tests"])).toBe(true);
    expect(kindMatches(["tests"], ["TESTS"])).toBe(true);
  });

  it("does not match an empty kind set", () => {
    // Load-bearing: pluginForKind relies on this to tell a stream tab from
    // the overview, which is available for every project.
    expect(kindMatches([], ["tests", "test"])).toBe(false);
  });

  it("matches any alias", () => {
    expect(kindMatches(["cov"], ["coverage", "cov", "conv"])).toBe(true);
  });
});

describe("tab ids", () => {
  it("are unique", () => {
    const ids = STREAM_KINDS.map((k) => k.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("claim no alias twice", () => {
    const seen = new Set<string>();
    for (const k of STREAM_KINDS) {
      for (const alias of k.aliases) {
        expect(seen.has(alias)).toBe(false);
        seen.add(alias);
      }
    }
  });
});

describe("kind resolution", () => {
  it("routes coverage to the conv tab", () => {
    // `conv` is the short URL for Coverage; the kind on disk is `coverage`.
    expect(tabForKind("coverage")?.id).toBe("conv");
    expect(tabForKind("cov")?.id).toBe("conv");
  });

  it("routes every kind the fixtures publish", () => {
    for (const kind of ["tests", "coverage", "benchmark", "regression", "molrec", "conformance"]) {
      expect(tabForKind(kind), kind).not.toBeNull();
    }
  });

  it("returns null for a kind nothing claims", () => {
    expect(tabForKind("fuzzing")).toBeNull();
  });
});
