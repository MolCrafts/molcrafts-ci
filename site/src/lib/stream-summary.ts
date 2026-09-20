/**
 * What one snapshot stream says about itself.
 *
 * The overview has to state a project's posture in one row per stream, and the
 * payload shape differs per kind. These are pure functions over an already
 * fetched snapshot so the rules stay readable and testable.
 */
import type { SnapshotStatus } from "@/components/snapshot-status";
import {
  asRecord,
  formatNumber,
  num,
  readCoverage,
  readMeasure,
  readScalars,
  readTests,
  type MeasureReading,
} from "@/lib/payload";
import type { IndexEntry, Snapshot } from "@/lib/snapshot-data";

export interface StreamVerdict {
  status: SnapshotStatus;
  /** What the status means for this stream, e.g. "passed", "3 failed". */
  statusLabel: string;
}

export interface HistoryPoint {
  entry: IndexEntry;
  /** null when that generation's body is unreadable or carries no scalar. */
  measure: MeasureReading | null;
  failed: boolean;
}

export interface StreamSummary extends StreamVerdict {
  /** The profile the history is plotted for; a series must not mix them. */
  profile: string | null;
  /** The project's own spelling of the kind, as published. */
  kind: string;
  /** Every published generation, newest first. The publish log reads these. */
  entries: IndexEntry[];
  /** Newest entry in the index, or null when the index is empty. */
  entry: IndexEntry | null;
  /** Body of the newest snapshot, so the inspector needs no second fetch. */
  snapshot: Snapshot | null;
  /** Oldest first, so a chart reads left to right. Capped by the provider. */
  history: HistoryPoint[];
  /** The one number a reader scans this row for. */
  headline: string;
}

/**
 * Reading order across the whole app: what needs attention first.
 *
 * The overview table, the navigator and the problems tab all sort by this, so
 * a failing stream is in the same place wherever the reader looks.
 */
export const STATUS_ORDER: SnapshotStatus[] = [
  "failed",
  "warning",
  "running",
  "queued",
  "completed",
  "cached",
  "ready",
  "draft",
  "cancelled",
];

/**
 * The verdict a snapshot carries for itself.
 *
 * Only a pass/fail count is a verdict the schema actually records. Coverage
 * targets and benchmark thresholds are not in the snapshot schema yet, so those
 * streams report `ready` — published, no verdict — rather than borrowing a
 * threshold this code invented.
 */
export function verdictOf(payload: unknown): StreamVerdict {
  const tests = readTests(payload);
  if (!tests) return { status: "ready", statusLabel: "no verdict" };
  if (tests.failed > 0) return { status: "failed", statusLabel: `${tests.failed} failed` };
  return { status: "completed", statusLabel: "passed" };
}

/**
 * The headline for a stream row.
 *
 * Keyed on what the payload contains rather than on the kind name, so a project
 * that spells a kind differently still gets a real headline.
 */
export function headlineOf(payload: unknown): string {
  const tests = readTests(payload);
  if (tests) return `${tests.passed} passed · ${tests.failed} failed`;

  const coverage = readCoverage(payload);
  if (coverage?.totals.lines != null) return `${coverage.totals.lines.toFixed(1)}% lines`;

  const p = asRecord(payload);
  const mean = p ? num(asRecord(p.metrics)?.mean_ns) : null;
  if (mean != null) return `${formatNumber(mean)} ns mean`;

  const maxAbs = p ? num(p.max_abs_error) : null;
  if (maxAbs != null) return `${formatNumber(maxAbs)} max abs error`;

  const first = readScalars(payload)[0];
  return first ? `${first.label} ${first.value}` : "—";
}

/**
 * One point per generation whose body was read, oldest first.
 *
 * Restricted to a single profile. A stream can publish the same commit under
 * several profiles — `molrs/benchmark` ships linux-x86_64 and macos-aarch64 of
 * one commit — and laying those along a time axis would draw a trend out of
 * two machines rather than two moments.
 */
export function toHistory(
  bodies: { entry: IndexEntry; snapshot: Snapshot | null }[],
  profile: string | null,
): HistoryPoint[] {
  return [...bodies]
    .filter(({ entry }) => (entry.profile ?? null) === profile)
    .reverse()
    .map(({ entry, snapshot }) => ({
      entry,
      measure: snapshot ? readMeasure(snapshot.payload) : null,
      failed: snapshot ? verdictOf(snapshot.payload).status === "failed" : false,
    }));
}

export function summarise(
  kind: string,
  entries: IndexEntry[],
  bodies: { entry: IndexEntry; snapshot: Snapshot | null }[],
): StreamSummary {
  const entry = entries[0] ?? null;
  const snapshot = bodies[0]?.snapshot ?? null;
  const profile = entry?.profile ?? null;
  if (!entry) {
    return {
      kind,
      entries,
      entry: null,
      snapshot: null,
      profile: null,
      history: [],
      headline: "—",
      status: "draft",
      statusLabel: "no snapshot",
    };
  }
  return {
    kind,
    entries,
    entry,
    snapshot,
    profile,
    history: toHistory(bodies, profile),
    headline: snapshot ? headlineOf(snapshot.payload) : "—",
    ...(snapshot
      ? verdictOf(snapshot.payload)
      : { status: "ready" as const, statusLabel: "body unavailable" }),
  };
}
