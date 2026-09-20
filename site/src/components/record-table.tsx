import type { JSX } from "react";

import { CommitLink } from "@/components/commit-link";
import { RunLink } from "@/components/run-link";
import { RowsSkeleton } from "@/components/skeletons";
import { StatusMark } from "@/components/snapshot-status";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RecordSummary } from "@/lib/record-summary";
import { relativeTime } from "@/lib/snapshot-data";
import { cn } from "@/lib/utils";

export interface RecordTableProps {
  /** null while the project's indexes are being read. */
  records: RecordSummary[] | null;
  onOpen: (record: RecordSummary) => void;
  emptyTitle: string;
}

/**
 * Every record this project publishes, and what each one currently says.
 *
 * This is the overview's primary inventory. Each row carries a verdict and a
 * reading, so the table answers "where do I look next" rather than listing
 * identifiers — the failing record sorts first, which is `STATUS_ORDER`'s job.
 *
 * Commit and run sit per row because that is where they are true: records are
 * published by different CI runs at different commits, so the same two facts
 * in a project-level strip would be whichever record happened to sort first.
 *
 * The whole row opens the record; the first cell keeps a real button so the
 * keyboard reaches it, and the links live in their own cells — an anchor
 * inside a button is invalid and swallows the click.
 */
export function RecordTable({ records, onOpen, emptyTitle }: RecordTableProps): JSX.Element {
  if (records !== null && records.length === 0) {
    return <EmptyState title={emptyTitle} density="compact" />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Record</TableHead>
          <TableHead>Reading</TableHead>
          <TableHead className="w-28">Commit</TableHead>
          <TableHead className="w-16">Run</TableHead>
          <TableHead className="w-28 text-right">Published</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {records === null ? (
          <TableRow>
            <TableCell colSpan={5}>
              <RowsSkeleton />
            </TableCell>
          </TableRow>
        ) : (
          records.map((record) => (
            <TableRow
              key={record.record}
              className="cursor-pointer"
              onClick={() => onOpen(record)}
            >
              <TableCell>
                <span className="flex items-center gap-2">
                  <StatusMark status={record.status} />
                  <button
                    type="button"
                    className={cn(
                      "max-w-full truncate rounded-hairline text-left font-mono outline-none",
                      "focus-visible:ring-2 focus-visible:ring-ring",
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpen(record);
                    }}
                  >
                    {record.record}
                  </button>
                </span>
              </TableCell>
              <TableCell className="truncate tabular-nums">{record.headline}</TableCell>
              <TableCell className="text-muted-foreground">
                <CommitLink
                  repository={record.entry?.repository}
                  commit={record.entry?.commit}
                />
              </TableCell>
              <TableCell className="text-muted-foreground">
                <RunLink
                  repository={record.entry?.repository}
                  run={record.entry?.workflow_run}
                >
                  run
                </RunLink>
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {relativeTime(record.entry?.timestamp)}
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
