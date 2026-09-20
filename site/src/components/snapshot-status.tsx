import type { JSX } from "react";

import { cn } from "@/lib/utils";

/**
 * The MolCrafts status vocabulary, unchanged.
 *
 * These nine words are the constitution's, not this product's: a new one is a
 * constitution change, not a CI decision. Do not add `pending`, `error`,
 * `success` or `stopped` aliases here or in the API-facing types.
 */
export type SnapshotStatus =
  | "draft"
  | "ready"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "cached"
  | "warning";

/**
 * Literal class strings, because Tailwind scans source text — a template
 * `bg-status-${status}` would compile to nothing.
 */
const MARK: Record<SnapshotStatus, string> = {
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

const WASH: Record<SnapshotStatus, string> = {
  draft: "bg-status-draft-soft",
  ready: "bg-status-ready-soft",
  queued: "bg-status-queued-soft",
  running: "bg-status-running-soft",
  completed: "bg-status-completed-soft",
  failed: "bg-status-failed-soft",
  cancelled: "bg-status-cancelled-soft",
  cached: "bg-status-cached-soft",
  warning: "bg-status-warning-soft",
};

/**
 * The status dot.
 *
 * Never rendered alone: a colour on its own is unreadable in greyscale and to
 * colourblind users, so every caller pairs it with the word.
 */
export const StatusMark = ({
  status,
  className,
}: {
  status: SnapshotStatus;
  className?: string;
}): JSX.Element => (
  <span
    aria-hidden="true"
    className={cn("size-status-dot shrink-0 rounded-full", MARK[status], className)}
  />
);

export interface SnapshotStatusBadgeProps {
  status: SnapshotStatus;
  /** What the status means here — "passed", "no verdict", "3 failed". */
  label: string;
  className?: string;
}

/**
 * Status as a dot plus a word on a wash of its own role.
 *
 * The word carries the meaning and takes the normal foreground colour, so the
 * badge stays legible in both themes without a per-status text colour.
 */
export const SnapshotStatusBadge = ({
  status,
  label,
  className,
}: SnapshotStatusBadgeProps): JSX.Element => (
  <span
    className={cn(
      "inline-flex items-center gap-1 rounded-control px-2 py-1",
      "text-label font-medium text-foreground whitespace-nowrap",
      WASH[status],
      className,
    )}
  >
    <StatusMark status={status} />
    {label}
  </span>
);
