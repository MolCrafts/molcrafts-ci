import type { KindTabPlugin, ProjectContext } from "./types";

const registry: KindTabPlugin[] = [];

/** Register a kind-tab plugin. Safe to call at module load from any entry. */
export function registerPlugin(plugin: KindTabPlugin): void {
  const existing = registry.findIndex((p) => p.id === plugin.id);
  if (existing >= 0) {
    registry[existing] = plugin;
    return;
  }
  registry.push(plugin);
}

/** All registered plugins, sorted by order then id. */
export function listPlugins(): KindTabPlugin[] {
  return [...registry].sort((a, b) => {
    const ao = a.order ?? 100;
    const bo = b.order ?? 100;
    if (ao !== bo) return ao - bo;
    return a.id.localeCompare(b.id);
  });
}

/** Plugins available for the given project context. */
export function pluginsFor(ctx: ProjectContext): KindTabPlugin[] {
  return listPlugins().filter((p) => p.available(ctx));
}

/**
 * The tab that opens one on-disk kind, or null when nothing claims it.
 *
 * A kind-specific plugin answers `available` from the kinds it was given, so a
 * plugin that is also available for *no* kinds is a whole-project surface (the
 * overview) rather than a stream tab — that is the test used here, so the
 * lookup does not have to know any plugin by name.
 */
export function pluginForKind(projectId: string, kind: string): KindTabPlugin | null {
  const empty: ProjectContext = { id: projectId, kinds: [] };
  const single: ProjectContext = { id: projectId, kinds: [kind] };
  return listPlugins().find((p) => p.available(single) && !p.available(empty)) ?? null;
}
