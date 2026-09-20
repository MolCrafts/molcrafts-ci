/**
 * One owner for published snapshot data.
 *
 * Every surface reads the same two things — a kind's index (`data/index/<project>/<kind>.jsonl`)
 * and a snapshot body (`data/<path>`) — so the fetchers, the alias table, and the
 * "which entry is current" rule live here rather than once per tab.
 */

/** One line of a published `<kind>.jsonl` index. */
export interface IndexEntry {
  snapshot_id?: string;
  path?: string;
  kind?: string;
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

/** A snapshot file: the manifest the producer wrote plus its kind-specific payload. */
export interface Snapshot<P = unknown> {
  manifest?: {
    kind?: string;
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
 * On-disk kind names a tab answers to.
 *
 * `conv` is the short URL for Coverage; the snapshot kind on disk is `coverage`.
 */
export const KIND_ALIASES: {
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
export function resolveKind(kinds: string[], aliases: string[]): string | null {
  const lower = new Map(kinds.map((k) => [k.toLowerCase(), k]));
  for (const alias of aliases) {
    const hit = lower.get(alias.toLowerCase());
    if (hit) return hit;
  }
  return null;
}

export async function fetchKindEntries(
  projectId: string,
  kind: string,
): Promise<IndexEntry[]> {
  const url = `./data/index/${encodeURIComponent(projectId)}/${encodeURIComponent(kind)}.jsonl`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) return [];
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

export async function fetchSnapshot<P>(entry: IndexEntry): Promise<Snapshot<P> | null> {
  if (!entry.path) return null;
  const url = `./data/${entry.path.replace(/^\.?\/?/, "")}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) return null;
  try {
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
