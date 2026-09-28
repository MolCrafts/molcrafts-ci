import { describe, expect, it } from "@rstest/core";

import { openRecord } from "@/lib/open-record";
import "@/plugins/builtins";

describe("openRecord", () => {
  it("resolves the tab for a published record", () => {
    expect(openRecord("molpy", "coverage")).toEqual({ tab: "conv" });
    expect(openRecord("molpy", "tests")).toEqual({ tab: "tests" });
  });

  it("pins a generation when given a snapshot id", () => {
    expect(openRecord("molpy", "tests", "tests-abc")).toEqual({
      tab: "tests",
      snapshot: "tests-abc",
    });
  });

  it("returns null when nothing claims the record", () => {
    expect(openRecord("molpy", "fuzzing")).toBeNull();
  });
});
