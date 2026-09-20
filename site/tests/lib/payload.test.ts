import { describe, expect, it } from "@rstest/core";

import {
  formatNumber,
  readCoverage,
  readMeasure,
  readScalars,
  readTests,
} from "@/lib/payload";

/* Payload shapes taken verbatim from the published fixtures in data/. */
const TESTS = { passed: 418, failed: 0 };
const TESTS_FAILING = { passed: 184, failed: 3 };
const COVERAGE = {
  totals: { branches: 68.9, functions: 88.0, lines: 82.3, statements: 81.5 },
  files: [
    { lines: 90.1, path: "molpy/core/frame.py", uncovered: [55, 56] },
    { lines: 74.0, path: "molpy/io/xyz.py", uncovered: [12, 13, 40] },
  ],
};
const BENCH_PYTEST = { metrics: { mean_ns: 12.5 } }; // molpy, pytest-benchmark
const BENCH_CRITERION = { suite: "neighbor_list" }; // molrs, criterion
const REGRESSION = { max_abs_error: 1.2e-8 };
const MOLREC = { schema_version: "0.1.0" };

describe("readTests", () => {
  it("reads a pass/fail count", () => {
    expect(readTests(TESTS)).toEqual({ passed: 418, failed: 0 });
  });

  it("treats failures/errors as the failed count", () => {
    expect(readTests({ failures: 2 })?.failed).toBe(2);
    expect(readTests({ errors: 5 })?.failed).toBe(5);
  });

  it("returns null when there is no verdict to read", () => {
    expect(readTests(COVERAGE)).toBeNull();
    expect(readTests(null)).toBeNull();
    expect(readTests([1, 2, 3])).toBeNull();
  });
});

describe("readCoverage", () => {
  it("reads totals and files", () => {
    const c = readCoverage(COVERAGE);
    expect(c?.totals.lines).toBe(82.3);
    expect(c?.files).toHaveLength(2);
  });

  it("survives a payload with totals but no files", () => {
    expect(readCoverage({ totals: { lines: 50 } })?.files).toEqual([]);
  });

  it("drops file rows with no path rather than rendering blanks", () => {
    const c = readCoverage({ totals: { lines: 1 }, files: [{ lines: 9 }, { path: "a.py" }] });
    expect(c?.files.map((f) => f.path)).toEqual(["a.py"]);
  });
});

describe("readMeasure", () => {
  it("picks the number worth plotting, per shape not per kind name", () => {
    expect(readMeasure(TESTS)).toMatchObject({ label: "passed", value: 418 });
    expect(readMeasure(COVERAGE)).toMatchObject({ label: "lines", value: 82.3, unit: "%" });
    expect(readMeasure(BENCH_PYTEST)).toMatchObject({ label: "mean", value: 12.5, unit: "ns" });
    expect(readMeasure(REGRESSION)).toMatchObject({ label: "max abs error", value: 1.2e-8 });
  });

  it("knows which direction is an improvement", () => {
    // A benchmark getting slower is worse; a coverage percentage rising is better.
    expect(readMeasure(BENCH_PYTEST)?.higherIsBetter).toBe(false);
    expect(readMeasure(REGRESSION)?.higherIsBetter).toBe(false);
    expect(readMeasure(COVERAGE)?.higherIsBetter).toBe(true);
  });

  it("returns null when a producer publishes no number", () => {
    // molrs ships criterion `{suite}` and molrec ships `{schema_version}`:
    // both real, both unplottable. The tile must say so rather than draw a
    // chart out of nothing.
    expect(readMeasure(BENCH_CRITERION)).toBeNull();
    expect(readMeasure(MOLREC)).toBeNull();
  });
});

describe("readScalars", () => {
  it("flattens one level so nested metrics still say something", () => {
    expect(readScalars(BENCH_PYTEST)).toEqual([
      { label: "metrics.mean_ns", value: "12.5", numeric: true },
    ]);
  });

  it("keeps strings and booleans, marked non-numeric", () => {
    expect(readScalars(MOLREC)).toEqual([
      { label: "schema_version", value: "0.1.0", numeric: false },
    ]);
  });
});

describe("formatNumber", () => {
  it("uses scientific notation only where a decimal would be unreadable", () => {
    expect(formatNumber(12.5)).toBe("12.5");
    expect(formatNumber(1601)).toBe("1601");
    expect(formatNumber(1.2e-8)).toBe("1.2e-8");
    expect(formatNumber(0)).toBe("0");
  });
});
