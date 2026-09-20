import { History } from "lucide-react";
import type { JSX } from "react";

import { relativeTime, shortCommit, type IndexEntry } from "@/lib/snapshot-data";

/**
 * How many generations the picker offers.
 *
 * A record tab answers one question — what does *this* snapshot say — so the
 * picker only has to reach the recent past. The complete history belongs to
 * the overview, where it is read as a series rather than as a list of
 * identifiers.
 */
export const HISTORY_LIMIT = 10;

export interface HistorySelectProps {
  /** Newest first; null while the index is being read. */
  entries: IndexEntry[] | null;
  selectedId: string | null;
  onSelect: (snapshotId: string) => void;
}

/** `6e01106 · 2 h ago`, falling back to the id when the entry carries neither. */
function optionLabel(entry: IndexEntry, index: number): string {
  const parts = [shortCommit(entry.commit), relativeTime(entry.timestamp)].filter(
    (p) => p && p !== "—",
  );
  return parts.length > 0
    ? parts.join(" · ")
    : (entry.snapshot_id ?? `generation ${index + 1}`);
}

/**
 * Which published generation this tab is reading.
 *
 * A native select rather than a menu primitive: ten options is the case the
 * platform control is good at, and it brings keyboard handling, type-ahead and
 * the mobile picker without a new dependency. Shaped after `ProfileSelect`, so
 * the two controls in this header read as one family.
 */
export function HistorySelect({
  entries,
  selectedId,
  onSelect,
}: HistorySelectProps): JSX.Element | null {
  if (entries === null || entries.length === 0) return null;

  const shown = entries.slice(0, HISTORY_LIMIT);
  const hidden = entries.length - shown.length;

  return (
    <div className="flex min-w-0 items-center gap-2">
      <label
        className="flex min-w-0 items-center gap-1.5 text-label text-muted-foreground"
        title="Published generation"
      >
        <History className="size-icon-sm shrink-0" aria-hidden="true" />
        <span className="sr-only">Published generation</span>
        <select
          className="h-control-compact min-w-0 rounded-control border border-border bg-surface px-2 font-mono text-label text-foreground"
          value={selectedId ?? ""}
          onChange={(e) => onSelect(e.target.value)}
        >
          {shown.map((entry, i) => (
            <option key={entry.snapshot_id ?? i} value={entry.snapshot_id ?? ""}>
              {optionLabel(entry, i)}
            </option>
          ))}
        </select>
      </label>
      {hidden > 0 && (
        <span className="text-micro whitespace-nowrap text-muted-foreground">
          newest {HISTORY_LIMIT} of {entries.length}
        </span>
      )}
    </div>
  );
}
