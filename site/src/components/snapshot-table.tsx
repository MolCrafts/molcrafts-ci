import type { JSX } from "react";

import { CommitLink } from "@/components/commit-link";
import { RowsSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { relativeTime, type IndexEntry } from "@/lib/snapshot-data";
import { cn } from "@/lib/utils";

export interface SnapshotTableProps {
  /** Newest first; null while the index is being read. */
  entries: IndexEntry[] | null;
  selectedId: string | null;
  onSelect: (snapshotId: string) => void;
  /** Shown when the index resolved empty. */
  emptyTitle: string;
  emptyDescription?: string;
}

/**
 * Every published generation of one record.
 *
 * The detail tab's job is the complete inventory, so this carries no verdict
 * and no headline — the overview already stated those. Selecting a row is what
 * points the inspector and the payload view at a generation.
 */
/*
 * The whole row is the target.
 *
 * A link in the first cell is a few characters wide; the reader aims at the
 * row. The row carries the pointer handler and the cell keeps a real <button>
 * so the keyboard can still reach it — an onClick on the <tr> alone would be
 * skipped by Tab.
 */
export function SnapshotTable({
  entries,
  selectedId,
  onSelect,
  emptyTitle,
  emptyDescription,
}: SnapshotTableProps): JSX.Element {
  if (entries !== null && entries.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} density="compact" />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Snapshot</TableHead>
          <TableHead className="w-28">Commit</TableHead>
          <TableHead className="w-20 text-right">Gen</TableHead>
          <TableHead className="w-28 text-right">Published</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries === null ? (
          <TableRow>
            <TableCell colSpan={4}>
              <RowsSkeleton />
            </TableCell>
          </TableRow>
        ) : (
          entries.map((entry, i) => {
            const on = entry.snapshot_id != null && entry.snapshot_id === selectedId;
            return (
              <TableRow
                key={entry.snapshot_id ?? `${entry.path ?? "row"}-${i}`}
                data-state={on ? "selected" : undefined}
                className="cursor-pointer"
                onClick={() => entry.snapshot_id && onSelect(entry.snapshot_id)}
              >
                <TableCell className="truncate font-mono">
                  <button
                    type="button"
                    className={cn(
                      "max-w-full truncate rounded-hairline text-left outline-none",
                      "focus-visible:ring-2 focus-visible:ring-ring",
                      on ? "text-foreground" : "text-foreground",
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (entry.snapshot_id) onSelect(entry.snapshot_id);
                    }}
                  >
                    {entry.snapshot_id ?? entry.path ?? `entry ${i + 1}`}
                  </button>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <CommitLink repository={entry.repository} commit={entry.commit} />
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {entry.generation ?? "—"}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {relativeTime(entry.timestamp)}
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
