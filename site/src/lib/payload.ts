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

/** Scientific notation where a decimal would be unreadable, plain otherwise. */
export function formatNumber(v: number): string {
  if (v !== 0 && (Math.abs(v) < 1e-3 || Math.abs(v) >= 1e6)) return v.toExponential(1);
  return String(v);
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
}

/** A test payload: the one record whose result is a verdict the schema records. */
export function readTests(payload: unknown): TestsReading | null {
  const p = asRecord(payload);
  if (!p) return null;
  const passed = num(p.passed);
  const failed = num(p.failed) ?? num(p.failures) ?? num(p.errors);
  if (passed == null && failed == null) return null;
  return { passed: passed ?? 0, failed: failed ?? 0 };
}

export interface ScalarField {
  label: string;
  value: string;
  /** Set when the value is a quantity, so the view can align it. */
  numeric: boolean;
}

function scalar(label: string, v: unknown): ScalarField | null {
  if (typeof v === "number" && Number.isFinite(v)) {
    return { label, value: formatNumber(v), numeric: true };
  }
  if (typeof v === "string" || typeof v === "boolean") {
    return { label, value: String(v), numeric: false };
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
export function readMeasure(payload: unknown): MeasureReading | null {
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

  const first = readScalars(payload).find((s) => s.numeric);
  if (!first) return null;
  return { label: first.label, value: Number(first.value), higherIsBetter: true };
}
