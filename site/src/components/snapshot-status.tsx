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
