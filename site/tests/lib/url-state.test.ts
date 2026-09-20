import { describe, expect, it } from "@rstest/core";

import {
  EMPTY_URL_STATE,
  formatHash,
  isNavigation,
  mergeUrlState,
  parseHash,
} from "@/lib/url-state";

describe("parseHash", () => {
  it("reads project, tab and refinements", () => {
    expect(parseHash("#/molpy/conv?profile=linux-x86_64&snapshot=cov-abc")).toEqual({
      project: "molpy",
      tab: "conv",
      profile: "linux-x86_64",
      snapshot: "cov-abc",
    });
  });

  it("accepts a bare project", () => {
    expect(parseHash("#/molpy")).toEqual({ ...EMPTY_URL_STATE, project: "molpy" });
  });

  it("returns empty state for no hash", () => {
    expect(parseHash("")).toEqual(EMPTY_URL_STATE);
    expect(parseHash("#")).toEqual(EMPTY_URL_STATE);
  });

  it("decodes project names that need escaping", () => {
    expect(parseHash("#/molcrafts-molrec/tests").project).toBe("molcrafts-molrec");
  });
});

describe("formatHash", () => {
  it("round-trips through parseHash", () => {
    const state = {
      project: "molrs",
      tab: "benchmark",
      profile: "macos-aarch64",
      snapshot: "bench-1",
    };
    expect(parseHash(formatHash(state))).toEqual(state);
  });

  it("omits absent refinements", () => {
    expect(formatHash({ ...EMPTY_URL_STATE, project: "molpy", tab: "tests" })).toBe(
      "#/molpy/tests",
    );
  });

  it("is empty without a project, so a fresh load has a clean address", () => {
    expect(formatHash(EMPTY_URL_STATE)).toBe("");
  });
});

describe("isNavigation", () => {
  const at = { project: "molpy", tab: "tests", profile: null, snapshot: null };

  it("counts project and tab as navigation", () => {
    expect(isNavigation(at, { tab: "conv" })).toBe(true);
    expect(isNavigation(at, { project: "molrs" })).toBe(true);
  });

  it("does not count refinements, so Back skips them", () => {
    expect(isNavigation(at, { profile: "linux-x86_64" })).toBe(false);
    expect(isNavigation(at, { snapshot: "s1" })).toBe(false);
  });

  it("does not count a no-op", () => {
    expect(isNavigation(at, { tab: "tests" })).toBe(false);
  });
});

describe("mergeUrlState", () => {
  const at = { project: "molpy", tab: "tests", profile: "linux-x86_64", snapshot: "s1" };

  it("drops a snapshot id that the new tab cannot contain", () => {
    expect(mergeUrlState(at, { tab: "conv" }).snapshot).toBeNull();
    expect(mergeUrlState(at, { project: "molrs" }).snapshot).toBeNull();
  });

  it("keeps an explicitly supplied snapshot across the move", () => {
    // Restoring a shared link sets project, tab and snapshot in one patch.
    expect(mergeUrlState(at, { tab: "conv", snapshot: "s2" }).snapshot).toBe("s2");
  });

  it("leaves the rest alone when only refining", () => {
    expect(mergeUrlState(at, { profile: "macos-aarch64" })).toEqual({
      ...at,
      profile: "macos-aarch64",
    });
  });
});
