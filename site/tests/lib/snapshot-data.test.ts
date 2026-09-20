import { describe, expect, it } from "@rstest/core";

import { projectsFromListing } from "@/lib/index-data";
import {
  RECORD_ALIASES,
  newestFirst,
  relativeTime,
  resolveRecord,
  shortCommit,
} from "@/lib/snapshot-data";

describe("newestFirst", () => {
  it("orders by timestamp, not by append order", () => {
    // The index is appended to, so the last line is not necessarily current.
    const rows = [
      { snapshot_id: "a", timestamp: "2026-09-18T09:12:00Z" },
      { snapshot_id: "b", timestamp: "2026-09-20T08:05:00Z" },
    ];
    expect(newestFirst(rows).map((r) => r.snapshot_id)).toEqual(["b", "a"]);
  });

  it("does not mutate its input", () => {
    const rows = [{ timestamp: "2026-01-01T00:00:00Z" }, { timestamp: "2026-02-01T00:00:00Z" }];
    const before = [...rows];
    newestFirst(rows);
    expect(rows).toEqual(before);
  });

  it("tolerates entries with no timestamp", () => {
    expect(newestFirst([{ snapshot_id: "x" }, { timestamp: "2026-01-01T00:00:00Z" }])).toHaveLength(
      2,
    );
  });
});

describe("resolveRecord", () => {
  it("returns the project's own spelling, not the alias asked for", () => {
    expect(resolveRecord(["Coverage"], RECORD_ALIASES.coverage)).toBe("Coverage");
  });

  it("prefers the first alias that matches", () => {
    expect(resolveRecord(["conv", "coverage"], RECORD_ALIASES.coverage)).toBe("coverage");
  });

  it("returns null when the project publishes none of them", () => {
    expect(resolveRecord(["tests"], RECORD_ALIASES.coverage)).toBeNull();
  });
});

describe("shortCommit", () => {
  it("takes seven characters", () => {
    expect(shortCommit("c3d4e5f60718293a4b5c6d7e8f901234")).toBe("c3d4e5f");
  });

  it("shows a dash rather than an empty cell", () => {
    expect(shortCommit(undefined)).toBe("—");
  });
});

describe("relativeTime", () => {
  const now = new Date("2026-09-20T12:00:00Z");

  it("scales the unit to the age", () => {
    expect(relativeTime("2026-09-20T11:30:00Z", now)).toBe("30 min ago");
    expect(relativeTime("2026-09-20T09:00:00Z", now)).toBe("3 h ago");
    expect(relativeTime("2026-09-10T12:00:00Z", now)).toBe("10 d ago");
  });

  it("returns the raw value rather than NaN when it cannot parse", () => {
    expect(relativeTime("not a date", now)).toBe("not a date");
    expect(relativeTime(undefined, now)).toBe("—");
  });
});

describe("projectsFromListing", () => {
  it("groups published index paths into projects and records", () => {
    const projects = projectsFromListing({
      indexes: [
        "data/index/molpy/tests.jsonl",
        "data/index/molpy/coverage.jsonl",
        "data/index/molrs/tests.jsonl",
      ],
    });
    expect(projects).toEqual([
      { id: "molpy", records: ["coverage", "tests"] },
      { id: "molrs", records: ["tests"] },
    ]);
  });

  it("ignores paths that are not an index entry", () => {
    expect(
      projectsFromListing({ indexes: ["data/index/molpy", "README.md", "./data/index/x/y.jsonl"] }),
    ).toEqual([{ id: "x", records: ["y"] }]);
  });
});
