import type { JSX } from "react";

import { TrendChart } from "@/components/trend-chart";
import { Button, EmptyState, RowsSkeleton } from "@molcrafts/design";
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
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <ul className="grid grid-cols-1 gap-x-10 gap-y-4 xl:grid-cols-2">
      {records.map((record) => {
        const plotted = record.history.filter((p) => p.measure != null);
        const current = plotted[plotted.length - 1]?.measure ?? null;
        const change = deltaOf(record);

        return (
          /* The panel opens the record for pointer users; the record name is
             the real button so the keyboard reaches it. A chart cannot sit
             inside a button: it would lose its tooltips and its figure role. */
          <li
            key={record.record}
            className="flex cursor-pointer flex-col gap-2 rounded-panel p-3 transition-colors hover:bg-interactive"
            onClick={() => onOpen(record)}
          >
            <span className="flex items-baseline gap-3">
              <Button
                variant="link"
                size="content"
                className="text-body-lg text-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpen(record);
                }}
              >
                {record.record}
              </Button>
              <span className="flex-1" />
              <span className="text-heading font-semibold tabular-nums text-foreground">
                {current ? formatMeasure(current.value, current.unit) : "—"}
              </span>
              {change && (
                <span
                  className={cn(
                    "text-body tabular-nums",
                    change.better ? "text-status-completed-foreground" : "text-status-warning-foreground",
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
          </li>
        );
      })}
    </ul>
  );
}
