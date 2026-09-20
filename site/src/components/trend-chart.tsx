import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef, type JSX } from "react";

import { formatNumber } from "@/lib/payload";
import { useIsDark } from "@/lib/use-is-dark";
import { relativeTime, shortCommit } from "@/lib/snapshot-data";
import type { HistoryPoint } from "@/lib/record-summary";

/* Only what a single-series line needs; the rest of ECharts is not bundled. */
echarts.use([LineChart, GridComponent, TooltipComponent, SVGRenderer]);

/** Theme values live in CSS, so read them rather than duplicating hexes here. */
function token(el: HTMLElement, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim();
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
export function TrendChart({ points, height = 64 }: TrendChartProps): JSX.Element {
  const box = useRef<HTMLDivElement>(null);
  // Colours come from CSS tokens, so a theme flip has to repaint the canvas.
  const dark = useIsDark();

  useEffect(() => {
    const el = box.current;
    if (!el) return;

    const chart = echarts.init(el, undefined, { renderer: "svg" });
    const plotted = points.filter((p) => p.measure != null);
    const line = token(el, "--mc-chart");
    const failed = token(el, "--status-failed");
    const muted = token(el, "--mc-text-muted");
    const surface = token(el, "--mc-surface");
    const border = token(el, "--mc-border");
    const ink = token(el, "--mc-text");

    chart.setOption({
      animation: false,
      grid: { top: 6, right: 6, bottom: 6, left: 6, containLabel: false },
      xAxis: { type: "category", show: false, data: plotted.map((p) => p.entry.snapshot_id ?? "") },
      yAxis: { type: "value", show: false, scale: true },
      tooltip: {
        trigger: "axis",
        borderColor: border,
        backgroundColor: surface,
        textStyle: { color: ink, fontSize: 12 },
        extraCssText: "border-radius:10px;box-shadow:0 12px 32px rgb(20 32 46 / 18%);",
        formatter: (params: unknown) => {
          const first = (params as { dataIndex: number }[])[0];
          const p = first ? plotted[first.dataIndex] : undefined;
          if (!p) return "";
          const value = p.measure ? formatNumber(p.measure.value) + (p.measure.unit ?? "") : "—";
          return [
            `<b>${value}</b>`,
            shortCommit(p.entry.commit),
            relativeTime(p.entry.timestamp),
            p.failed ? "failed" : "",
          ]
            .filter(Boolean)
            .join(" &middot; ");
        },
      },
      series: [
        {
          type: "line",
          data: plotted.map((p) => p.measure?.value ?? null),
          smooth: false,
          showSymbol: plotted.length === 1,
          symbolSize: 7,
          lineStyle: { width: 2, color: line },
          itemStyle: {
            color: (p: { dataIndex: number }) => (plotted[p.dataIndex]?.failed ? failed : line),
          },
          // Only failures and the current point are marked; a dot on every
          // generation is noise the line already carries.
          markPoint: {
            symbol: "circle",
            symbolSize: 8,
            label: { show: false },
            data: plotted.flatMap((p, i) =>
              p.failed || i === plotted.length - 1
                ? [
                    {
                      xAxis: i,
                      yAxis: p.measure?.value ?? 0,
                      itemStyle: {
                        color: p.failed ? failed : line,
                        borderColor: surface,
                        borderWidth: 2,
                      },
                    },
                  ]
                : [],
            ),
          },
          emphasis: { itemStyle: { color: muted } },
        },
      ],
    });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [points, dark]);

  return <div ref={box} style={{ height }} className="w-full" aria-hidden="true" />;
}
