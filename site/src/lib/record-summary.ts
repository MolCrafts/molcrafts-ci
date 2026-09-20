/**
 * What one snapshot record says about itself.
 *
 * The overview has to state a project's posture in one row per record, and the
 * payload shape differs per record. These are pure functions over an already
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

export interface RecordVerdict {
  status: SnapshotStatus;
  /** What the status means for this record, e.g. "passed", "3 failed". */
  statusLabel: string;
}

export interface HistoryPoint {
  entry: IndexEntry;
  /** null when that generation's body is unreadable or carries no scalar. */
  measure: MeasureReading | null;
  failed: boolean;
}

export interface RecordSummary extends RecordVerdict {
  /** The profile everything in this summary is read at; never mixed. */
  profile: string | null;
  /** Every profile this record publishes under, so a selector can offer them. */
  profiles: string[];
  /** The project's own spelling of the record, as published. */
  record: string;
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
 * a failing record is in the same place wherever the reader looks.
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
 * records report `ready` — published, no verdict — rather than borrowing a
 * threshold this code invented.
 */
export function verdictOf(payload: unknown): RecordVerdict {
  const tests = readTests(payload);
  if (!tests) return { status: "ready", statusLabel: "no verdict" };
  if (tests.failed > 0) return { status: "failed", statusLabel: `${tests.failed} failed` };
  return { status: "completed", statusLabel: "passed" };
}

/**
 * The headline for a record row.
 *
 * Keyed on what the payload contains rather than on the record name, so a project
 * that spells a record differently still gets a real headline.
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
 * Restricted to a single profile. A record can publish the same commit under
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

/** Every profile a record publishes under, sorted, with unprofiled last. */
export function profilesOf(entries: IndexEntry[]): string[] {
  return [...new Set(entries.flatMap((e) => (e.profile ? [e.profile] : [])))].sort();
}

/**
 * One record, read at one profile.
 *
 * The profile decides everything downstream — headline, status and series all
 * come from the same machine. Reading the status from the newest entry while
 * charting a different profile would put two machines in one row.
 *
 * `preferred` is the project-wide choice; a record that does not publish it
 * falls back to its own newest entry rather than rendering empty.
 */
export function summarise(
  record: string,
  entries: IndexEntry[],
  bodies: { entry: IndexEntry; snapshot: Snapshot | null }[],
  preferred: string | null = null,
): RecordSummary {
  const profiles = profilesOf(entries);
  const profile =
    preferred && profiles.includes(preferred) ? preferred : (entries[0]?.profile ?? null);

  const inProfile = entries.filter((e) => (e.profile ?? null) === profile);
  const entry = inProfile[0] ?? null;
  const snapshot = bodies.find(({ entry: e }) => e.snapshot_id === entry?.snapshot_id)?.snapshot ?? null;

  if (!entry) {
    return {
      record,
      entries,
      entry: null,
      snapshot: null,
      profile,
      profiles,
      history: [],
      headline: "—",
      status: "draft",
      statusLabel: "no snapshot",
    };
  }

  return {
    record,
    entries,
    entry,
    snapshot,
    profile,
    profiles,
    history: toHistory(bodies, profile),
    headline: snapshot ? headlineOf(snapshot.payload) : "—",
    ...(snapshot
      ? verdictOf(snapshot.payload)
      : { status: "ready" as const, statusLabel: "body unavailable" }),
  };
}
