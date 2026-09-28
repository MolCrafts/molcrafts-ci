import { defineMolplotChart } from "@molcrafts/molplot";
import { createElement, useMemo, type JSX } from "react";

import { formatMeasure } from "@/lib/payload";
import type { HistoryPoint } from "@/lib/record-summary";
import { relativeTime, shortCommit } from "@/lib/snapshot-data";
import { useIsDark } from "@/lib/use-is-dark";

defineMolplotChart();

/** Theme values live in CSS, so read them rather than duplicating hexes here. */
function token(el: HTMLElement | null, name: string, fallback: string): string {
  if (!el) return fallback;
  const value = getComputedStyle(el).getPropertyValue(name).trim();
  return value || fallback;
}

function sparklineSpec(
  points: HistoryPoint[],
  colors: { line: string; failed: string; surface: string },
): string {
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
  return JSON.stringify({
    padding: 2,
    background: null,
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
  });
}

export interface TrendChartProps {
  points: HistoryPoint[];
  height?: number;
}

/**
 * One record's measure over its generations.
 *
 * One series, so no legend — the tile names it. Generations that failed are
 * marked in the status ramp; the line itself never carries state. No gridlines
 * and no axis labels: at this size they are noise, and the tooltip carries the
 * exact values.
 */
export function TrendChart({ points, height = 72 }: TrendChartProps): JSX.Element {
  // Colours come from CSS tokens, so a theme flip has to rebuild the spec.
  const dark = useIsDark();
  const spec = useMemo(() => {
    const root = typeof document !== "undefined" ? document.documentElement : null;
    return sparklineSpec(points, {
      line: token(root, "--mc-chart", dark ? "#00a9a4" : "#008f8c"),
      failed: token(root, "--status-failed", "#c44"),
      surface: token(root, "--mc-surface", dark ? "#0f1419" : "#fff"),
    });
  }, [points, dark]);

  return createElement("molplot-chart", {
    key: `${dark ? "dark" : "light"}:${spec.length}:${points.length}`,
    className: "trend-sparkline",
    preset: "molplot",
    theme: dark ? "dark" : "light",
    interactive: "false",
    width: "100%",
    spec,
    style: {
      display: "block",
      width: "100%",
      height,
      maxWidth: "none",
      aspectRatio: "unset",
      // Compact sparkline: no inner air (molplot surface inset tracks this).
      ["--molplot-pad" as string]: "0px",
      padding: 0,
      overflow: "hidden",
    },
    "aria-hidden": "true",
  });
}
