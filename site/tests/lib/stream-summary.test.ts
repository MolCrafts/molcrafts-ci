import { describe, expect, it } from "@rstest/core";

import type { IndexEntry, Snapshot } from "@/lib/snapshot-data";
import { headlineOf, summarise, toHistory, verdictOf } from "@/lib/stream-summary";

const entry = (over: Partial<IndexEntry> = {}): IndexEntry => ({
  snapshot_id: "s1",
  path: "snapshots/x.json",
  kind: "tests",
  generation: 1,
  profile: "linux-x86_64",
  commit: "c3d4e5f60718293a4b5c6d7e8f901234",
  timestamp: "2026-09-20T08:05:00Z",
  ...over,
});

const body = (payload: unknown): Snapshot => ({ payload });

describe("verdictOf", () => {
  it("reports failure only when the payload counts one", () => {
    expect(verdictOf({ passed: 184, failed: 3 })).toEqual({
      status: "failed",
      statusLabel: "3 failed",
    });
    expect(verdictOf({ passed: 418, failed: 0 }).status).toBe("completed");
  });

  it("says 'no verdict' rather than inventing one", () => {
    // Coverage targets and benchmark thresholds are not in the schema, so a
    // coverage payload must not be scored as pass or fail.
    expect(verdictOf({ totals: { lines: 82.3 } })).toEqual({
      status: "ready",
      statusLabel: "no verdict",
    });
    expect(verdictOf(undefined).status).toBe("ready");
  });
});

describe("headlineOf", () => {
  it("summarises each real payload shape", () => {
    expect(headlineOf({ passed: 418, failed: 0 })).toBe("418 passed · 0 failed");
    expect(headlineOf({ totals: { lines: 82.3 } })).toBe("82.3% lines");
    expect(headlineOf({ metrics: { mean_ns: 12.5 } })).toBe("12.5 ns mean");
    expect(headlineOf({ max_abs_error: 1.2e-8 })).toBe("1.2e-8 max abs error");
  });

  it("falls back to the first scalar for a shape it has never seen", () => {
    expect(headlineOf({ suite: "neighbor_list" })).toBe("suite neighbor_list");
  });

  it("returns a dash rather than throwing on junk", () => {
    expect(headlineOf(null)).toBe("—");
    expect(headlineOf({})).toBe("—");
  });
});

describe("toHistory", () => {
  it("returns points oldest first, so a chart reads left to right", () => {
    const bodies = [
      { entry: entry({ snapshot_id: "new", timestamp: "2026-09-20T00:00:00Z" }), snapshot: body({ passed: 418 }) },
      { entry: entry({ snapshot_id: "old", timestamp: "2026-09-18T00:00:00Z" }), snapshot: body({ passed: 412 }) },
    ];
    expect(toHistory(bodies, "linux-x86_64").map((p) => p.entry.snapshot_id)).toEqual([
      "old",
      "new",
    ]);
  });

  it("keeps a series to one profile", () => {
    // molrs/benchmark publishes the same commit under linux-x86_64 and
    // macos-aarch64. Laying those along a time axis would draw a trend out of
    // two machines rather than two moments.
    const bodies = [
      { entry: entry({ snapshot_id: "linux", profile: "linux-x86_64" }), snapshot: body({ passed: 1 }) },
      { entry: entry({ snapshot_id: "macos", profile: "macos-aarch64" }), snapshot: body({ passed: 2 }) },
    ];
    const kept = toHistory(bodies, "linux-x86_64");
    expect(kept).toHaveLength(1);
    expect(kept[0]?.entry.snapshot_id).toBe("linux");
  });

  it("marks the generations that failed", () => {
    const bodies = [
      { entry: entry({ snapshot_id: "a" }), snapshot: body({ passed: 1, failed: 2 }) },
      { entry: entry({ snapshot_id: "b" }), snapshot: body({ passed: 3, failed: 0 }) },
    ];
    expect(toHistory(bodies, "linux-x86_64").map((p) => p.failed)).toEqual([false, true]);
  });

  it("keeps a point whose body could not be read, with no measure", () => {
    const bodies = [{ entry: entry(), snapshot: null }];
    expect(toHistory(bodies, "linux-x86_64")[0]?.measure).toBeNull();
  });
});

describe("summarise", () => {
  it("plots the profile of the newest entry", () => {
    const entries = [entry({ snapshot_id: "new", profile: "macos-aarch64" }), entry({ snapshot_id: "old" })];
    const s = summarise("benchmark", entries, [
      { entry: entries[0]!, snapshot: body({ passed: 1 }) },
      { entry: entries[1]!, snapshot: body({ passed: 2 }) },
    ]);
    expect(s.profile).toBe("macos-aarch64");
    expect(s.history).toHaveLength(1);
  });

  it("reports an empty index as draft rather than as a failure", () => {
    const s = summarise("tests", [], []);
    expect(s.status).toBe("draft");
    expect(s.entry).toBeNull();
    expect(s.history).toEqual([]);
  });
});
