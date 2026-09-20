/**
 * One owner for published snapshot data.
 *
 * Every surface reads the same two things — a record's index
 * (`index/<project>/<record>.jsonl`) and a snapshot body (`<entry.path>`) — so
 * the fetchers, the alias table, and the "which entry is current" rule live
 * here rather than once per tab. Both resolve against the data root through
 * `dataUrl`, which is what decides whether that root is bundled or the
 * published `data` branch.
 */

import { dataUrl } from "@/lib/data-source";

/** One line of a published `<record>.jsonl` index. */
export interface IndexEntry {
  snapshot_id?: string;
  path?: string;
  record?: string;
  generation?: number;
  profile?: string;
  producer?: string;
  repository?: string;
  commit?: string;
  ref?: string;
  timestamp?: string;
  workflow_run?: number;
  [key: string]: unknown;
}

/** A snapshot file: the manifest the producer wrote plus its record-specific payload. */
export interface Snapshot<P = unknown> {
  manifest?: {
    record?: string;
    producer?: string;
    profile?: string;
    schema_version?: string;
    source?: {
      commit?: string;
      ref?: string;
      repository?: string;
      timestamp?: string;
      workflow_run?: number;
      producer_version?: string | null;
    };
    tracking?: { enabled?: boolean; generation?: number };
  };
  payload?: P;
}

/**
 * On-disk record names a tab answers to.
 *
 * `conv` is the short URL for Coverage; the snapshot record on disk is `coverage`.
 */
export const RECORD_ALIASES: {
  tests: string[];
  coverage: string[];
  benchmark: string[];
  regression: string[];
  molrec: string[];
  conformance: string[];
} = {
  tests: ["tests", "test"],
  coverage: ["coverage", "cov", "conv"],
  benchmark: ["benchmark"],
  regression: ["regression", "numerical"],
  molrec: ["molrec"],
  conformance: ["conformance"],
};

/** The project's own spelling of the first alias it publishes, or null. */
export function resolveRecord(records: string[], aliases: string[]): string | null {
  const lower = new Map(records.map((k) => [k.toLowerCase(), k]));
  for (const alias of aliases) {
    const hit = lower.get(alias.toLowerCase());
    if (hit) return hit;
  }
  return null;
}

export async function fetchRecordEntries(
  projectId: string,
  record: string,
): Promise<IndexEntry[]> {
  const url = dataUrl(
    `index/${encodeURIComponent(projectId)}/${encodeURIComponent(record)}.jsonl`,
  );
  const res = await fetch(url, { cache: "no-store" });
  // The listing said this index exists, so a non-OK response is a failure to
  // read it, not an absence of history. Rendering it as "no snapshots" blamed
  // the producer for the reader's problem.
  if (!res.ok) {
    throw new Error(`Cannot read ${record} for ${projectId}: ${res.status} ${res.statusText}`);
  }
  const entries: IndexEntry[] = [];
  for (const line of (await res.text()).split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      entries.push(JSON.parse(trimmed) as IndexEntry);
    } catch {
      /* a malformed line loses that entry, not the whole index */
    }
  }
  return entries;
}

/**
 * One snapshot body, or null.
 *
 * Total on purpose — it never rejects. One unreadable body should cost its own
 * panel, not the page: callers render "body unavailable" and move on. A
 * rejection used to escape here and leave every caller's `settled` flag false,
 * so a transient CDN failure left a skeleton on screen forever.
 */
export async function fetchSnapshot<P>(entry: IndexEntry): Promise<Snapshot<P> | null> {
  if (!entry.path) return null;
  try {
    const res = await fetch(dataUrl(entry.path), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Snapshot<P>;
  } catch {
    return null;
  }
}

/** Index order is append order, so "current" is the newest timestamp, not the last line. */
export function newestFirst(entries: IndexEntry[]): IndexEntry[] {
  return [...entries].sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? ""));
}

export function shortCommit(commit: string | undefined): string {
  return commit ? commit.slice(0, 7) : "—";
}

/** Coarse age, for a column the user scans rather than reads. */
export function relativeTime(iso: string | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso;
  const mins = Math.round((now.getTime() - then) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}
