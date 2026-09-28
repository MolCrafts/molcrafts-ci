import { pluginForRecord } from "@/plugins/registry";

/**
 * URL patch that opens a record's tab, optionally pinned to one generation.
 *
 * Overview, the dock and any future surface that says "go look at this record"
 * go through here, so record→tab resolution has one owner.
 */
export function openRecord(
  projectId: string,
  record: string,
  snapshotId?: string | null,
): { tab: string; snapshot?: string | null } | null {
  const tab = pluginForRecord(projectId, record)?.id;
  if (!tab) return null;
  if (snapshotId === undefined) return { tab };
  return { tab, snapshot: snapshotId };
}
