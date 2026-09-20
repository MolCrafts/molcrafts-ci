import type { JSX } from "react";

import { RowsSkeleton } from "@/components/skeletons";
import { SnapshotStatusBadge } from "@/components/snapshot-status";
import { EmptyState } from "@/components/ui/empty-state";
import { formatNumber } from "@/lib/payload";
import { relativeTime, shortCommit } from "@/lib/snapshot-data";
import type { HistoryPoint, StreamSummary } from "@/lib/stream-summary";
import { cn } from "@/lib/utils";

const W = 240;
const H = 52;
const PAD = 5;

/**
 * One stream's measure over its published generations.
 *
 * A single hue, because there is one series — a legend would name what the tile
 * already says. Generations that failed are marked in the status ramp, which is
 * the one place a status colour belongs here; the line itself never carries
 * state. No gridlines: with no y axis to read against, they would be noise.
 */
function TrendLine({ points, label }: { points: HistoryPoint[]; label: string }): JSX.Element {
  const plotted = points.filter((p) => p.measure != null);
  const values = plotted.map((p) => p.measure?.value ?? 0);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || Math.abs(hi) || 1;
  const n = plotted.length;

  const x = (i: number) => (n === 1 ? W / 2 : PAD + (i / (n - 1)) * (W - PAD * 2));
  const y = (v: number) => H - PAD - ((v - lo) / span) * (H - PAD * 2);

  const describe = (p: HistoryPoint) =>
    `${shortCommit(p.entry.commit)} · ${relativeTime(p.entry.timestamp)} · ` +
    `${p.measure ? formatNumber(p.measure.value) : "—"}${p.measure?.unit ?? ""}` +
    `${p.failed ? " · failed" : ""}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height={H}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${label} over ${n} generation${n === 1 ? "" : "s"}`}
      className="overflow-visible"
    >
      {/* Hairline baseline, no gridlines. */}
      <line
        x1={0}
        y1={H - 0.5}
        x2={W}
        y2={H - 0.5}
        stroke="var(--mc-border)"
        strokeWidth={1}
        vectorEffect="non-scaling-stroke"
      />
      {n > 1 && (
        <polyline
          points={plotted.map((p, i) => `${x(i)},${y(p.measure?.value ?? 0)}`).join(" ")}
          fill="none"
          stroke="var(--mc-chart)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
      {plotted.map((p, i) => {
        const last = i === n - 1;
        if (!p.failed && !last) {
          // Only the current point and the failures are marked; a dot on every
          // generation is the noise the line already carries.
          return (
            <circle key={i} cx={x(i)} cy={y(p.measure?.value ?? 0)} r={6} fill="transparent">
              <title>{describe(p)}</title>
            </circle>
          );
        }
        return (
          <circle
            key={i}
            cx={x(i)}
            cy={y(p.measure?.value ?? 0)}
            r={4}
            fill={p.failed ? "var(--status-failed)" : "var(--mc-chart)"}
            stroke="var(--mc-surface)"
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
          >
            <title>{describe(p)}</title>
          </circle>
        );
      })}
    </svg>
  );
}

/** Signed change against the previous generation, in ink — never a verdict. */
function Delta({ points }: { points: HistoryPoint[] }): JSX.Element | null {
  const plotted = points.filter((p) => p.measure != null);
  const current = plotted[plotted.length - 1]?.measure;
  const previous = plotted[plotted.length - 2]?.measure;
  if (!current || !previous) return null;

  const change = current.value - previous.value;
  if (change === 0) return <span className="text-label text-muted-foreground">unchanged</span>;

  return (
    <span className="font-mono text-label tabular-nums text-muted-foreground">
      {change > 0 ? "↑" : "↓"} {formatNumber(Math.abs(change))}
      {current.unit ?? ""}
    </span>
  );
}

export interface StreamTrendsProps {
  streams: StreamSummary[] | null;
  onOpen: (stream: StreamSummary) => void;
  emptyTitle: string;
  emptyDescription?: string;
}

/**
 * The project's history, one tile per stream.
 *
 * Small multiples rather than one plot: passes, percentages, nanoseconds and
 * absolute error share no axis, and putting them on one would invent a
 * relationship that is not in the data.
 */
export function StreamTrends({
  streams,
  onOpen,
  emptyTitle,
  emptyDescription,
}: StreamTrendsProps): JSX.Element {
  if (streams === null) return <RowsSkeleton rows={3} />;
  if (streams.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} density="compact" />;
  }

  return (
    <ul className="grid grid-cols-1 gap-x-8 lg:grid-cols-2">
      {streams.map((stream) => {
        const plotted = stream.history.filter((p) => p.measure != null);
        const current = plotted[plotted.length - 1]?.measure ?? null;
        const failures = stream.history.filter((p) => p.failed).length;

        return (
          <li key={stream.kind} className="border-b border-border py-3">
            <button
              type="button"
              className={cn(
                "flex w-full flex-col gap-2 rounded-control px-2 py-1 text-left outline-none",
                "hover:bg-interactive focus-visible:ring-2 focus-visible:ring-ring",
              )}
              onClick={() => onOpen(stream)}
            >
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-body font-medium text-foreground">
                  {stream.kind}
                </span>
                <SnapshotStatusBadge status={stream.status} label={stream.statusLabel} />
                <span className="flex-1" />
                <Delta points={stream.history} />
              </div>

              {current ? (
                <>
                  <div className="flex items-baseline gap-2">
                    {/* Proportional figures: a standalone value, not a column. */}
                    <span className="text-title font-semibold text-foreground">
                      {formatNumber(current.value)}
                      {current.unit ?? ""}
                    </span>
                    <span className="text-label text-muted-foreground">{current.label}</span>
                  </div>
                  <TrendLine points={stream.history} label={current.label} />
                </>
              ) : (
                <p className="py-2 text-label text-muted-foreground">
                  {stream.headline === "—"
                    ? "Nothing readable in this snapshot."
                    : `No number to plot — this producer publishes ${stream.headline}.`}
                </p>
              )}

              <div className="flex items-baseline gap-3 text-micro text-muted-foreground">
                <span className="font-mono tabular-nums">
                  {plotted.length} generation{plotted.length === 1 ? "" : "s"}
                </span>
                {plotted.length === 1 && <span>no trend yet</span>}
                {stream.profile && <span className="font-mono">{stream.profile}</span>}
                {failures > 0 && (
                  <span className="font-mono tabular-nums">{failures} failed</span>
                )}
                <span className="flex-1" />
                <span>{relativeTime(stream.entry?.timestamp)}</span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
