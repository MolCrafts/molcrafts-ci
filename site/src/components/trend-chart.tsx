import { useMemo, type JSX } from "react";
import { VegaLiteView, type VegaLiteSpec, type ChartTheme } from "@molcrafts/design-vega-lite";
import { formatMeasure } from "@/lib/payload";
import type { HistoryPoint } from "@/lib/record-summary";
import { relativeTime, shortCommit } from "@/lib/snapshot-data";

function sparklineSpec(
  points: HistoryPoint[],
  colors: { line: string; failed: string; surface: string },
): VegaLiteSpec {
  const plotted = points.filter((p) => p.measure != null);
  const values = plotted.map((p, i) => {
    const value = p.measure ? formatMeasure(p.measure.value, p.measure.unit) : "—";
    const tip = [
      value,
      shortCommit(p.entry.commit),
      relativeTime(p.entry.timestamp),
      p.failed ? "failed" : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return {
      i,
      y: p.measure?.value ?? null,
      tip,
      // Emphasise failures and the current point; every point still draws.
      emphasis: p.failed || i === plotted.length - 1,
      failed: p.failed,
    };
  });

  // Size comes from the host box (RawChart measures it) — do not set
  // width/height here or they override the fitted numeric size.
  return {
    padding: 2,
    autosize: { type: "fit", contains: "padding" },
    background: "transparent",
    data: { values },
    layer: [
      {
        mark: {
          type: "line",
          strokeWidth: 2,
          stroke: colors.line,
          interpolate: "linear",
          tooltip: true,
        },
        encoding: {
          x: {
            field: "i",
            type: "quantitative",
            axis: null,
            scale: { nice: false, zero: false, padding: 0 },
          },
          y: {
            field: "y",
            type: "quantitative",
            axis: null,
            scale: { zero: false, nice: false },
          },
          tooltip: { field: "tip", type: "nominal" },
        },
      },
      {
        mark: {
          type: "point",
          filled: true,
          stroke: colors.surface,
          strokeWidth: 1,
          tooltip: true,
        },
        encoding: {
          x: {
            field: "i",
            type: "quantitative",
            axis: null,
            scale: { nice: false, zero: false, padding: 0 },
          },
          y: {
            field: "y",
            type: "quantitative",
            axis: null,
            scale: { zero: false, nice: false },
          },
          size: {
            condition: { test: "datum.emphasis", value: 56 },
            value: 28,
          },
          color: {
            condition: { test: "datum.failed", value: colors.failed },
            value: colors.line,
          },
          opacity: {
            condition: { test: "datum.emphasis", value: 1 },
            value: 0.55,
          },
          tooltip: { field: "tip", type: "nominal" },
        },
      },
    ],
    config: {
      view: { stroke: null },
      style: { cell: { stroke: null } },
      axis: { grid: false, ticks: false, domain: false, labels: false, title: null },
    },
  };
}

export interface TrendChartProps { points: HistoryPoint[]; height?: number; }

/** CI owns the history mapping; the optional Design adapter owns compilation/rendering. */
export function TrendChart({ points, height = 72 }: TrendChartProps): JSX.Element {
  const spec = useMemo(() => (theme: ChartTheme) => sparklineSpec(points, {
    line: theme.primary, failed: theme.danger, surface: theme.background,
  }), [points]);
  const plotted = points.filter(point => point.measure != null);
  const summary = plotted.map(point => `${shortCommit(point.entry.commit)}: ${formatMeasure(point.measure!.value, point.measure!.unit)}${point.failed ? " (failed)" : ""}`).join("; ");
  return <VegaLiteView label="Record measurement history" spec={spec} height={height}
    empty={plotted.length === 0} className="trend-sparkline"
    style={{ overflow: "hidden" }} aria-description={summary || "No measurements"} />;
}
