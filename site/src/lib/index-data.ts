import { dataUrl } from "@/lib/data-source";
import type { ProjectContext } from "@/plugins/types";

export interface IndexListing {
  indexes: string[];
  /**
   * Newest index timestamp per project, written by `molci ingest`.
   * Older listings omit it; those projects sort alphabetically.
   */
  published?: Record<string, string>;
}

/**
 * Parse published index paths into per-project record sets.
 * Paths look like: data/index/<project>/<record>.jsonl
 *
 * Order is whatever published last, first — the bare visit opens the first
 * entry, and alphabetical said nothing about which project just ran.
 */
export function projectsFromListing(listing: IndexListing): ProjectContext[] {
  const byId = new Map<string, Set<string>>();

  for (const raw of listing.indexes) {
    const normalized = raw.replace(/^\.\//, "").replace(/^\/+/, "");
    const parts = normalized.split("/");
    const indexAt = parts.indexOf("index");
    if (indexAt < 0 || parts.length < indexAt + 3) continue;
    const project = parts[indexAt + 1];
    const file = parts[indexAt + 2];
    if (!project || !file?.endsWith(".jsonl")) continue;
    const record = file.slice(0, -".jsonl".length);
    if (!record) continue;
    let set = byId.get(project);
    if (!set) {
      set = new Set();
      byId.set(project, set);
    }
    set.add(record);
  }

  const published = listing.published ?? {};
  return [...byId.entries()]
    .map(([id, records]) => ({
      id,
      records: [...records].sort(),
    }))
    .sort((a, b) => {
      const at = published[a.id];
      const bt = published[b.id];
      if (!at && !bt) return a.id.localeCompare(b.id);
      if (!at) return 1;
      if (!bt) return -1;
      return bt.localeCompare(at) || a.id.localeCompare(b.id);
    });
}

export async function loadIndexListing(): Promise<IndexListing> {
  const res = await fetch(dataUrl("index-listing.json"), { cache: "no-store" });
  if (!res.ok) {
    // Returning an empty listing here told the reader that CI had published
    // nothing, when the truth was that the site could not read it. Since the
    // index moved to the `data` branch this is a cross-origin request to a
    // CDN, so the difference is one a reader will actually meet.
    throw new Error(`Cannot read the index listing: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as IndexListing;
  return { indexes: data.indexes ?? [], published: data.published };
}
