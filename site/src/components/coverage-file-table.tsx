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

/** How many files the table shows before deferring to the CI run. */
export const COVERAGE_FILE_LIMIT = 10;

/** Uncovered lines in a file, preferring the producer's count over a capped list. */
export function uncoveredCount(file: CoverageFile): number {
  return file.uncoveredTotal ?? file.uncovered?.length ?? 0;
}

/**
 * The files most worth a test, and only those.
 *
 * Sorted by uncovered lines, not by percentage. Percentage put a three-line
 * `__init__.py` at 0% above an eight-hundred-line module at 60%, which is the
 * opposite of where the next test belongs — and the docstring here used to
 * claim the sort it did not compute.
 *
 * Line numbers are gone. Four hundred comma-separated integers is the payload
 * printed, not information: nobody reads it, and rendering it unwrapped is
 * what grew the work surface past sixteen thousand pixels. The count is the
 * scannable form, and the full report is in the CI run this snapshot names.
 */
export function CoverageFileTable({ files }: { files: CoverageFile[] }): JSX.Element {
  const worst = [...files]
    .filter((f) => uncoveredCount(f) > 0)
    .sort((a, b) => uncoveredCount(b) - uncoveredCount(a))
    .slice(0, COVERAGE_FILE_LIMIT);

  if (worst.length === 0) {
    return (
      <p className="py-2 text-label text-muted-foreground">
        Every measured file is fully covered.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File</TableHead>
          <TableHead className="w-48">Lines</TableHead>
          <TableHead className="w-32 text-right">Uncovered</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {worst.map((file) => (
          <TableRow key={file.path}>
            <TableCell className="max-w-0 truncate font-mono" title={file.path}>
              {file.path}
            </TableCell>
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
            <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
              {uncoveredCount(file)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
