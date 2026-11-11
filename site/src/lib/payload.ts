/**
 * Reading a snapshot payload by its shape.
 *
 * Producers differ per record and per project, and the record name is only a hint —
 * `molrs` publishes `benchmark` from criterion while `molpy` publishes it from
 * pytest-benchmark. So every reader here keys on what the payload *contains*.
 * A hand-written view per record name would drift the first time a project spells
 * one differently.
 */

export function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

export function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export const SCIENTIFIC_BENCHMARK_SCHEMA = "atomiverse.scientific-benchmark/1";

export interface ScientificBenchmark {
  schema: typeof SCIENTIFIC_BENCHMARK_SCHEMA;
  campaign_id: string;
  summary: {
    required: number;
    passed: number;
    failed: number;
    incomplete: number;
    optional_unavailable: number;
    complete: boolean;
    performance_regressions: number;
    historical_status: string;
  };
  matrix: {
    columns: string[];
    rows: { id: string; label: string; systems: string[]; values: Record<string, string[]>; notes: string }[];
  };
  environment: Record<string, unknown>;
  source: Record<string, unknown>;
  protocol: Record<string, unknown>;
  threads: number;
  repeats: number;
  warmup: number;
  started: string;
  roadmap: Record<string, unknown>[];
  results: Record<string, unknown>[];
}

/** Recognise the domain before generic readers, including unsupported versions. */
export function isScientificBenchmark(payload: unknown, producer?: string): boolean {
  const p = asRecord(payload), schema = p?.schema;
  return producer === "atomiverse-benchmarks"
    || (typeof schema === "string" && schema.startsWith("atomiverse.scientific-benchmark"))
    || !!(p && "campaign_id" in p && "matrix" in p && "summary" in p);
}

function count(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function text(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function texts(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(text);
}

/**
 * Validate the published display contract, not scientific tolerances or ratios.
 * Invalid/unsupported bundles must never fall through to generic test counts.
 */
export function readScientificBenchmark(payload: unknown): ScientificBenchmark | null {
  const p = asRecord(payload);
  if (!p || p.schema !== SCIENTIFIC_BENCHMARK_SCHEMA || !text(p.campaign_id)) return null;
  const s = asRecord(p.summary), m = asRecord(p.matrix), e = asRecord(p.environment);
  if (!s || !m || !e || !asRecord(p.source) || !asRecord(p.protocol)) return null;
  for (const key of ["required", "passed", "failed", "incomplete", "optional_unavailable", "performance_regressions"]) {
    if (!count(s[key])) return null;
  }
  const required = s.required as number, passed = s.passed as number;
  const failed = s.failed as number, incomplete = s.incomplete as number;
  if (passed + failed + incomplete !== required || typeof s.complete !== "boolean"
      || s.complete !== (failed === 0 && incomplete === 0) || !text(s.historical_status)) return null;
  if (!texts(m.columns) || m.columns.length === 0 || new Set(m.columns).size !== m.columns.length
      || !Array.isArray(m.rows) || m.rows.length === 0) return null;
  const ids = new Set<string>();
  for (const raw of m.rows) {
    const row = asRecord(raw), values = row && asRecord(row.values);
    if (!row || !text(row.id) || ids.has(row.id) || !text(row.label)
        || !texts(row.systems) || row.systems.length === 0 || !values
        || typeof row.notes !== "string" || Object.keys(values).length !== m.columns.length) return null;
    ids.add(row.id);
    for (const col of m.columns) {
      if (!Object.hasOwn(values, col) || !texts(values[col]) || values[col].length === 0) return null;
    }
  }
  if (!(e.cpu_model === null || typeof e.cpu_model === "string") || !text(e.os) || !text(e.python)
      || !Array.isArray(e.gpus) || !e.gpus.every(g => typeof g === "string" || asRecord(g))) return null;
  for (const key of ["physical_cores", "logical_cpus", "host_memory_bytes"]) {
    if (e[key] !== null && !count(e[key])) return null;
  }
  if (!count(p.threads) || p.threads === 0 || !count(p.repeats) || p.repeats === 0
      || !count(p.warmup) || !text(p.started) || !Array.isArray(p.roadmap)
      || !p.roadmap.every(asRecord) || !Array.isArray(p.results)) return null;
  const totals = { pass: 0, fail: 0, unverified: 0 };
  const cells = new Set<string>();
  let optionalUnavailable = 0;
  for (const raw of p.results) {
    const result = asRecord(raw);
    if (!result || !text(result.row_id) || !ids.has(result.row_id)
        || !text(result.system_id) || !text(result.participant_id)
        || !m.columns.includes(result.participant_id) || typeof result.required !== "boolean"
        || !text(result.status) || !["pass", "fail", "unverified"].includes(String(result.numerical))) return null;
    const id = JSON.stringify([result.row_id, result.system_id, result.participant_id]);
    if (cells.has(id)) return null;
    cells.add(id);
    if (result.numerical === "pass" && result.status !== "completed") return null;
    if (result.required) totals[result.numerical as keyof typeof totals]++;
    else if (result.status !== "completed") optionalUnavailable++;
  }
  if (totals.pass !== passed || totals.fail !== failed || totals.unverified !== incomplete
      || optionalUnavailable !== s.optional_unavailable) return null;
  return p as unknown as ScientificBenchmark;
}

/** Scientific notation where a decimal would be unreadable, plain otherwise. */
export function formatNumber(v: number): string {
  if (v !== 0 && (Math.abs(v) < 1e-3 || Math.abs(v) >= 1e6)) return v.toExponential(1);
  return String(v);
}

/** Every percentage in this app keeps one decimal place — 88 → "88.0%". */
export function formatPercent(v: number | null | undefined): string {
  return v == null || Number.isNaN(v) ? "—" : `${v.toFixed(1)}%`;
}

/** Format a measure for tiles, tips and deltas. */
export function formatMeasure(value: number, unit?: string): string {
  if (unit === "%") return formatPercent(value);
  return unit ? `${formatNumber(value)} ${unit}` : formatNumber(value);
}

export interface CoverageTotals {
  lines?: number;
  branches?: number;
  functions?: number;
  statements?: number;
}

export interface CoverageFile {
  path: string;
  lines?: number;
  uncovered?: number[];
  /** Set by the producer when `uncovered` was capped, so a count can be true. */
  uncoveredTotal?: number;
}

export interface CoverageReading {
  totals: CoverageTotals;
  files: CoverageFile[];
}

/** A coverage payload: percentage totals, optionally with per-file rows. */
export function readCoverage(payload: unknown): CoverageReading | null {
  const p = asRecord(payload);
  const totals = p ? asRecord(p.totals) : null;
  if (!p || !totals) return null;

  const files: CoverageFile[] = Array.isArray(p.files)
    ? p.files.flatMap((raw) => {
        const f = asRecord(raw);
        const path = f && typeof f.path === "string" ? f.path : null;
        if (!path) return [];
        return [
          {
            path,
            lines: num(f?.lines) ?? undefined,
            uncovered: Array.isArray(f?.uncovered)
              ? f.uncovered.filter((n): n is number => typeof n === "number")
              : undefined,
            uncoveredTotal: num(f?.uncovered_total) ?? undefined,
          },
        ];
      })
    : [];

  return {
    totals: {
      lines: num(totals.lines) ?? undefined,
      branches: num(totals.branches) ?? undefined,
      functions: num(totals.functions) ?? undefined,
      statements: num(totals.statements) ?? undefined,
    },
    files,
  };
}

export interface TestsReading {
  passed: number;
  failed: number;
  /** Counted separately: a skipped test is neither a pass nor a failure. */
  skipped: number;
}

/** A test payload: the one record whose result is a verdict the schema records. */
export function readTests(payload: unknown): TestsReading | null {
  const p = asRecord(payload);
  if (!p) return null;
  const passed = num(p.passed);
  const failed = num(p.failed) ?? num(p.failures) ?? num(p.errors);
  if (passed == null && failed == null) return null;
  // Dropping `skipped` made the total a lie on any suite that skips: the one
  // fact the line omitted was the one only the duplicate metric list carried.
  return { passed: passed ?? 0, failed: failed ?? 0, skipped: num(p.skipped) ?? 0 };
}

export interface ScalarField {
  label: string;
  /** For display: one decimal for percentages, scientific notation at the extremes. */
  value: string;
  /** The number as published, when the field is a quantity; never parsed back from `value`. */
  number: number | null;
}

function scalar(label: string, v: unknown): ScalarField | null {
  if (typeof v === "number" && Number.isFinite(v)) {
    // Coverage-ish field names keep one decimal; everything else stays free-form.
    const percentish = /(?:^|[._])(?:lines|branches|functions|statements|percent|pct)$/i.test(
      label,
    );
    return {
      label,
      value: percentish ? v.toFixed(1) : formatNumber(v),
      number: v,
    };
  }
  if (typeof v === "string" || typeof v === "boolean") {
    return { label, value: String(v), number: null };
  }
  return null;
}

/**
 * Every scalar a payload carries, one level deep.
 *
 * A nested object contributes its own scalars under `parent.child` rather than
 * being dropped — `{"metrics": {"mean_ns": 12.5}}` has to say something.
 */
export function readScalars(payload: unknown): ScalarField[] {
  const p = asRecord(payload);
  if (!p) return [];
  const out: ScalarField[] = [];
  for (const [key, value] of Object.entries(p)) {
    const flat = scalar(key, value);
    if (flat) {
      out.push(flat);
      continue;
    }
    const nested = asRecord(value);
    if (!nested) continue;
    for (const [childKey, childValue] of Object.entries(nested)) {
      const child = scalar(`${key}.${childKey}`, childValue);
      if (child) out.push(child);
    }
  }
  return out;
}

export interface MeasureReading {
  /** What the number is, in the producer's own word. */
  label: string;
  value: number;
  unit?: string;
  /**
   * Which direction is an improvement.
   *
   * A property of the measure, not a threshold: a benchmark getting slower is
   * worse whatever the budget is. Thresholds are not in the schema and are not
   * invented here.
   */
  higherIsBetter: boolean;
}

/**
 * The one number a record is worth plotting over time.
 *
 * Keyed on shape like every other reader here, so a producer this code has
 * never seen still contributes a series as long as it publishes a scalar.
 */
export function readMeasure(payload: unknown, producer?: string): MeasureReading | null {
  // A heterogeneous scientific matrix has no single meaningful time/error
  // scalar. Its declared summary is displayed directly, without a fake trend.
  if (isScientificBenchmark(payload, producer)) return null;
  const tests = readTests(payload);
  if (tests) {
    return { label: "passed", value: tests.passed, higherIsBetter: true };
  }

  const coverage = readCoverage(payload);
  if (coverage?.totals.lines != null) {
    return { label: "lines", value: coverage.totals.lines, unit: "%", higherIsBetter: true };
  }

  const p = asRecord(payload);
  const mean = p ? num(asRecord(p.metrics)?.mean_ns) : null;
  if (mean != null) return { label: "mean", value: mean, unit: "ns", higherIsBetter: false };

  const maxAbs = p ? num(p.max_abs_error) : null;
  if (maxAbs != null) return { label: "max abs error", value: maxAbs, higherIsBetter: false };

  const first = readScalars(payload).find((s) => s.number != null);
  if (!first || first.number == null) return null;
  return { label: first.label, value: first.number, higherIsBetter: true };
}
