import { describe, expect, it } from "@rstest/core";
import { readMeasure, readScientificBenchmark } from "@/lib/payload";
import { headlineOf, verdictOf } from "@/lib/record-summary";
import { scientificBenchmark } from "../fixtures/scientific-benchmark";

describe("scientific benchmark payload", () => {
  it("reads the complete matrix and actual environment without flattening it", () => {
    const b = scientificBenchmark();
    expect(readScientificBenchmark(b)).toEqual(b);
    expect(verdictOf(b)).toEqual({ status: "completed", statusLabel: "numerical passed · unbaselined" });
    expect(headlineOf(b)).toBe("4/4 numerical passed · 0 failed · 0 incomplete");
    expect(readMeasure(b)).toBeNull();
  });

  it("keeps failed and incomplete observations visible", () => {
    const b = scientificBenchmark();
    b.results[0]!.numerical = "fail";
    Object.assign(b.summary, { passed: 3, failed: 1, complete: false });
    expect(verdictOf(b)).toEqual({ status: "failed", statusLabel: "1 numerical failed" });
    b.results[0]!.numerical = "unverified";
    b.results[0]!.status = "timeout";
    Object.assign(b.summary, { failed: 0, incomplete: 1 });
    expect(verdictOf(b)).toEqual({ status: "warning", statusLabel: "1 incomplete" });
  });

  it("reports historical regressions independently of numerical completeness", () => {
    const b = scientificBenchmark();
    b.summary.performance_regressions = 1;
    b.summary.historical_status = "fail";
    expect(verdictOf(b)).toEqual({ status: "failed", statusLabel: "1 performance regressions" });
  });

  it("does not promote an empty required set", () => {
    const b = scientificBenchmark();
    b.results.forEach(r => { r.required = false; });
    Object.assign(b.summary, { required: 0, passed: 0 });
    expect(verdictOf(b).status).toBe("warning");
  });

  it("does not mistake a malformed producer payload with no schema for passing tests", () => {
    const payload = { passed: 999, failed: 0 };
    expect(verdictOf(payload, "atomiverse-benchmarks").status).toBe("warning");
    expect(headlineOf(payload, "atomiverse-benchmarks")).toBe("Invalid or unsupported scientific benchmark");
    expect(readMeasure(payload, "atomiverse-benchmarks")).toBeNull();
  });

  it.each([
    (b: any) => { b.schema = "atomiverse.scientific-benchmark/2"; },
    (b: any) => { delete b.schema; },
    (b: any) => { b.summary.failed = -1; },
    (b: any) => { b.summary.passed = NaN; },
    (b: any) => { b.summary.incomplete = "0"; },
    (b: any) => { b.summary.complete = false; },
    (b: any) => { b.results[0].numerical = "fail"; },
    (b: any) => { b.results[0].status = "timeout"; },
    (b: any) => { b.results.push(b.results[0]); },
    (b: any) => { delete b.matrix.rows[0].values["pyscf.cpu"]; },
    (b: any) => { b.matrix.rows[0].values["atv.cpu.direct"] = [null]; },
    (b: any) => { b.matrix.rows.push(b.matrix.rows[0]); },
    (b: any) => { b.matrix.columns.push("pyscf.cpu"); },
    (b: any) => { b.environment = {}; },
    (b: any) => { delete b.protocol; },
  ])("rejects malformed/contradictory scientific records before generic readers", mutate => {
    const b = scientificBenchmark();
    mutate(b);
    Object.assign(b, { passed: 999, failed: 0 });
    expect(readScientificBenchmark(b)).toBeNull();
    expect(verdictOf(b)).toEqual({ status: "warning", statusLabel: "invalid benchmark payload" });
    expect(headlineOf(b)).toBe("Invalid or unsupported scientific benchmark");
    expect(readMeasure(b)).toBeNull();
  });
});
