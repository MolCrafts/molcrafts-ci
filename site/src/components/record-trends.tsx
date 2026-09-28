import type { JSX } from "react";

import { RowsSkeleton } from "@/components/skeletons";
import { TrendChart } from "@/components/trend-chart";
import { EmptyState } from "@/components/ui/empty-state";
import { formatMeasure } from "@/lib/payload";
import { deltaOf, type RecordSummary } from "@/lib/record-summary";
import { cn } from "@/lib/utils";

export interface RecordTrendsProps {
  records: RecordSummary[] | null;
  onOpen: (record: RecordSummary) => void;
  emptyTitle: string;
  emptyDescription?: string;
}

/**
 * The project, as one panel per record.
 *
 * Small multiples: passes, percentages, nanoseconds and absolute error share
 * no axis, and one plot would invent a relationship the data does not have.
 *
 * Each panel answers only "how did this reading move": the current value, the
 * change against the previous generation, and the shape. Identity, status and
 * freshness live in the table above — repeating them here is what made an
 * earlier overview loud.
 */
export function RecordTrends({
  records,
  onOpen,
  emptyTitle,
  emptyDescription,
}: RecordTrendsProps): JSX.Element {
  if (records === null) return <RowsSkeleton rows={3} />;
  if (records.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} density="compact" />;
  }

  return (
    <ul className="grid grid-cols-1 gap-x-10 gap-y-2 xl:grid-cols-2">
      {records.map((record) => {
        const plotted = record.history.filter((p) => p.measure != null);
        const current = plotted[plotted.length - 1]?.measure ?? null;
        const change = deltaOf(record);

        return (
          <li key={record.record}>
            <button
              type="button"
              onClick={() => onOpen(record)}
              className={cn(
                "flex w-full flex-col gap-2 rounded-panel px-3 py-3 text-left outline-none",
                "hover:bg-interactive focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <span className="flex items-baseline gap-3">
                <span className="font-mono text-body text-foreground">{record.record}</span>
                <span className="flex-1" />
                <span className="font-mono text-display font-semibold tabular-nums text-foreground">
                  {current ? formatMeasure(current.value, current.unit) : "—"}
                </span>
                {change && (
                  <span
                    className={cn(
                      "font-mono text-label tabular-nums",
                      change.better ? "text-status-completed" : "text-status-warning",
                    )}
                  >
                    {change.text}
                  </span>
                )}
              </span>

              {current ? (
                <TrendChart points={record.history} />
              ) : (
                <span className="py-5 text-label text-muted-foreground">{record.statusLabel}</span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
