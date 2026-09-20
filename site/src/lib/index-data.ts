import { dataUrl } from "@/lib/data-source";
import type { ProjectContext } from "@/plugins/types";

export interface IndexListing {
  indexes: string[];
}

/**
 * Parse published index paths into per-project record sets.
 * Paths look like: data/index/<project>/<record>.jsonl
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

  return [...byId.entries()]
    .map(([id, records]) => ({
      id,
      records: [...records].sort(),
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

export async function loadIndexListing(): Promise<IndexListing> {
  const res = await fetch(dataUrl("index-listing.json"), { cache: "no-store" });
  if (!res.ok) {
    return { indexes: [] };
  }
  const data = (await res.json()) as IndexListing;
  return { indexes: data.indexes ?? [] };
}
