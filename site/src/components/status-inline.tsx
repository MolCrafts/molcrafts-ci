import type { JSX } from "react";

import { StatusMark, type SnapshotStatus } from "@/components/snapshot-status";
import { cn } from "@/lib/utils";

const FILL: Record<SnapshotStatus, string> = {
  draft: "bg-status-draft",
  ready: "bg-status-ready",
  queued: "bg-status-queued",
  running: "bg-status-running",
  completed: "bg-status-completed",
  failed: "bg-status-failed",
  cancelled: "bg-status-cancelled",
  cached: "bg-status-cached",
  warning: "bg-status-warning",
};

export interface StatusSegment {
  status: SnapshotStatus;
  count: number;
  label: string;
}

export interface StatusInlineProps {
  /** What is being counted — "4 streams", "187 tests". */
  total: string;
  segments: StatusSegment[];
  className?: string;
}

/**
 * How a set of children is doing, in one line.
 *
 * A distribution is decision-bearing — it says where to look next — so it earns
 * a place on an overview. The same counts as four equal tiles would not.
 */
export const StatusInline = ({ total, segments, className }: StatusInlineProps): JSX.Element => {
  const shown = segments.filter((s) => s.count > 0);
  const sum = shown.reduce((acc, s) => acc + s.count, 0);

  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-2", className)}>
      <span className="text-label text-muted-foreground whitespace-nowrap">{total}</span>
      {sum > 0 && (
        <div
          className="flex h-1 w-40 overflow-hidden rounded-hairline bg-sunken"
          role="img"
          aria-label={shown.map((s) => `${s.count} ${s.label}`).join(", ")}
        >
          {shown.map((s) => (
            <span
              key={s.status}
              className={FILL[s.status]}
              style={{ width: `${(s.count / sum) * 100}%` }}
            />
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {shown.map((s) => (
          <span key={s.status} className="inline-flex items-center gap-1 text-label">
            <StatusMark status={s.status} />
            <span className="font-mono tabular-nums text-foreground">{s.count}</span>
            <span className="text-muted-foreground">{s.label}</span>
          </span>
        ))}
      </div>
    </div>
  );
};
