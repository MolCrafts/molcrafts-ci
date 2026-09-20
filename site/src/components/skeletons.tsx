import type { JSX } from "react";

import { cn } from "@/lib/utils";

/**
 * One loading pattern for the whole product.
 *
 * Each skeleton is built from the same structure as the thing it stands in
 * for, rather than from a measured height, so it cannot drift out of step when
 * that thing changes — and so a surface does not jump when the fetch resolves.
 * "Still loading" must never read as an empty state.
 */

const PULSE = "animate-pulse rounded-hairline bg-sunken";

export interface BandSkeletonProps {
  /** `strip` mirrors MetaStrip; `measure` adds MeasureBand's bar. */
  height?: "strip" | "measure";
  className?: string;
}

export const BandSkeleton = ({ height = "strip", className }: BandSkeletonProps): JSX.Element => (
  <div
    aria-hidden="true"
    className={cn(
      "flex border-b border-border pb-3",
      className,
    )}
  >
    {Array.from({ length: height === "strip" ? 5 : 4 }, (_, i) => (
      <div
        key={i}
        className={cn(
          "flex flex-1 flex-col gap-hairline px-4",
          i === 0 && "pl-0",
          i > 0 && "border-l border-border",
        )}
      >
        <div className={cn("h-3 w-12", PULSE)} />
        <div className={cn("h-4 w-20", PULSE)} />
        {height === "measure" && <div className={cn("mt-1 h-1 w-full", PULSE)} />}
      </div>
    ))}
  </div>
);

export interface RowsSkeletonProps {
  rows?: number;
  className?: string;
}

export const RowsSkeleton = ({ rows = 4, className }: RowsSkeletonProps): JSX.Element => (
  <div aria-hidden="true" className={cn("flex flex-col gap-1", className)}>
    {Array.from({ length: rows }, (_, i) => (
      <div key={i} className={cn("h-8", PULSE)} />
    ))}
  </div>
);
