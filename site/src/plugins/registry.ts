import type { RecordTabPlugin, ProjectContext } from "./types";

const registry: RecordTabPlugin[] = [];

/** Register a record-tab plugin. Safe to call at module load from any entry. */
export function registerPlugin(plugin: RecordTabPlugin): void {
  const existing = registry.findIndex((p) => p.id === plugin.id);
  if (existing >= 0) {
    registry[existing] = plugin;
    return;
  }
  registry.push(plugin);
}

/** All registered plugins, sorted by order then id. */
export function listPlugins(): RecordTabPlugin[] {
  return [...registry].sort((a, b) => {
    const ao = a.order ?? 100;
    const bo = b.order ?? 100;
    if (ao !== bo) return ao - bo;
    return a.id.localeCompare(b.id);
  });
}

/** Plugins available for the given project context. */
export function pluginsFor(ctx: ProjectContext): RecordTabPlugin[] {
  return listPlugins().filter((p) => p.available(ctx));
}

/**
 * The tab that opens one on-disk record, or null when nothing claims it.
 *
 * A record-specific plugin answers `available` from the records it was given, so a
 * plugin that is also available for *no* records is a whole-project surface (the
 * overview) rather than a record tab — that is the test used here, so the
 * lookup does not have to know any plugin by name.
 */
export function pluginForRecord(projectId: string, record: string): RecordTabPlugin | null {
  const empty: ProjectContext = { id: projectId, records: [] };
  const single: ProjectContext = { id: projectId, records: [record] };
  return listPlugins().find((p) => p.available(single) && !p.available(empty)) ?? null;
}
