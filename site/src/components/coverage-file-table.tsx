import type { JSX } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CoverageFile } from "@/lib/payload";
import { cn } from "@/lib/utils";

/**
 * Where a percentage sits, as a reading aid on the bar only.
 *
 * No coverage target lives in the snapshot schema, so these bands colour the
 * measure; they do not claim a pass or a fail. Adding a real target is a schema
 * change first.
 */
export function coverageTone(value: number | undefined): string {
  if (value == null) return "bg-status-draft";
  if (value >= 85) return "bg-status-completed";
  if (value >= 70) return "bg-status-warning";
  return "bg-status-failed";
}

export function formatPercent(n: number | undefined): string {
  return n == null || Number.isNaN(n) ? "—" : `${n.toFixed(1)}%`;
}

/**
 * Per-file coverage, worst first.
 *
 * Sorted by what the reader acts on: the file most likely to need a test comes
 * first, rather than whatever order the producer emitted.
 */
export function CoverageFileTable({ files }: { files: CoverageFile[] }): JSX.Element {
  const sorted = [...files].sort((a, b) => (a.lines ?? 0) - (b.lines ?? 0));

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File</TableHead>
          <TableHead className="w-48">Lines</TableHead>
          <TableHead className="w-64">Uncovered</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((file) => (
          <TableRow key={file.path}>
            <TableCell className="truncate font-mono">{file.path}</TableCell>
            <TableCell>
              <span className="flex items-center gap-2">
                <span className="h-1 w-24 overflow-hidden rounded-hairline bg-sunken">
                  <span
                    className={cn("block h-full", coverageTone(file.lines))}
                    style={{ width: `${Math.max(0, Math.min(100, file.lines ?? 0))}%` }}
                  />
                </span>
                <span className="font-mono tabular-nums">{formatPercent(file.lines)}</span>
              </span>
            </TableCell>
            <TableCell className="truncate font-mono text-muted-foreground">
              {file.uncovered?.length ? file.uncovered.join(", ") : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
