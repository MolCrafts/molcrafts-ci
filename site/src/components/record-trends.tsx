import type { JSX } from "react";

import { RowsSkeleton } from "@/components/skeletons";
import { StatusMark } from "@/components/snapshot-status";
import { TrendChart } from "@/components/trend-chart";
import { EmptyState } from "@/components/ui/empty-state";
import { formatNumber } from "@/lib/payload";
import type { RecordSummary } from "@/lib/record-summary";

export interface RecordTrendsProps {
  records: RecordSummary[] | null;
  onOpen: (record: RecordSummary) => void;
  emptyTitle: string;
  emptyDescription?: string;
}

/**
 * The project, as one chart per record.
 *
 * Small multiples: passes, percentages, nanoseconds and absolute error share
 * no axis, and one plot would invent a relationship the data does not have.
 *
 * Each tile says three things: which record, what it reads now, and how it got
 * there. Change, freshness, commit and profile are all one click away in that
 * record's own tab, and the chart's tooltip carries them per point — repeating
 * them under every tile is what made the overview loud.
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
    <ul className="grid grid-cols-1 gap-x-10 gap-y-2 lg:grid-cols-2">
      {records.map((record) => {
        const plotted = record.history.filter((p) => p.measure != null);
        const current = plotted[plotted.length - 1]?.measure ?? null;
        const failing = record.status === "failed";

        return (
          <li
            key={record.record}
            className="cursor-pointer rounded-panel px-3 py-3 hover:bg-interactive"
            onClick={() => onOpen(record)}
          >
            <div className="flex items-baseline gap-2">
              {failing && <StatusMark status="failed" className="self-center" />}
              <button
                type="button"
                className="rounded-hairline font-mono text-body text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpen(record);
                }}
              >
                {record.record}
              </button>
              <span className="flex-1" />
              <span className="text-heading font-semibold tabular-nums text-foreground">
                {current ? formatNumber(current.value) + (current.unit ?? "") : "—"}
              </span>
            </div>

            {current ? (
              <TrendChart points={record.history} />
            ) : (
              <p className="py-5 text-label text-muted-foreground">{record.headline}</p>
            )}

          </li>
        );
      })}
    </ul>
  );
}
