import type { JSX } from "react";

import { cn } from "@/lib/utils";

export interface Metric {
  label: string;
  /** Already formatted — this component does not decide precision. */
  value: string;
  unit?: string;
}

export interface MetricTableProps {
  metrics: Metric[];
  /** Two columns once there are enough rows to make a single column tall. */
  columns?: 1 | 2;
  className?: string;
}

/**
 * The fields of one object: label left, quantity right.
 *
 * This is the property-list pattern, not a table of records — it is what a
 * payload of scalars should look like, instead of a card per number or a JSON
 * blob. Values are mono and tabular so digits line up down the column.
 */
export function MetricTable({ metrics, columns = 2, className }: MetricTableProps): JSX.Element {
  return (
    <dl
      className={cn(
        "grid gap-x-8",
        columns === 2 ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1",
        className,
      )}
    >
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="flex items-baseline justify-between gap-4 border-b border-border py-1 last:border-b-0"
        >
          <dt className="min-w-0 truncate text-label text-muted-foreground">{metric.label}</dt>
          <dd className="shrink-0 font-mono text-body tabular-nums text-foreground">
            {metric.value}
            {metric.unit && (
              <span className="ml-1 text-label text-muted-foreground">{metric.unit}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
