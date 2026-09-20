import type { JSX } from "react";

import { ContentSection } from "@/components/blocks/content-section";
import {
  CoverageFileTable,
  coverageTone,
  formatPercent,
} from "@/components/coverage-file-table";
import { MeasureBand, type Measure } from "@/components/meta-strip";
import { MetricTable, type Metric } from "@/components/metric-table";
import { BandSkeleton } from "@/components/skeletons";
import { StatusInline } from "@/components/status-inline";
import { EmptyState } from "@/components/ui/empty-state";
import { readCoverage, readScalars, readTests } from "@/lib/payload";

export interface PayloadViewProps {
  /** The selected snapshot's body; null while loading or when unreadable. */
  payload: unknown;
  loading?: boolean;
  /** True once the fetch settled, so null means unreadable rather than pending. */
  settled?: boolean;
}

/**
 * What one snapshot says, read from its shape.
 *
 * Dispatching on the payload rather than on the record name is what lets a new
 * producer land without a new view: `molrs` publishing criterion metrics and
 * `molpy` publishing pytest-benchmark metrics both arrive here as scalars.
 */
export function PayloadView({
  payload,
  loading = false,
  settled = true,
}: PayloadViewProps): JSX.Element {
  if (loading) return <BandSkeleton height="measure" />;

  if (payload == null) {
    return settled ? (
      <EmptyState title="Snapshot body unavailable" density="compact" />
    ) : (
      <BandSkeleton height="measure" />
    );
  }

  const coverage = readCoverage(payload);
  if (coverage) {
    const measures: Measure[] = (
      [
        ["Lines", coverage.totals.lines],
        ["Branches", coverage.totals.branches],
        ["Functions", coverage.totals.functions],
        ["Statements", coverage.totals.statements],
      ] as const
    ).map(([label, value]) => ({
      label,
      value: formatPercent(value),
      percent: value,
      tone: coverageTone(value),
    }));

    return (
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <MeasureBand measures={measures} />
        {coverage.files.length > 0 && (
          <ContentSection
            title="Files"
            action={
              <span className="font-mono text-label tabular-nums text-muted-foreground">
                {coverage.files.length}
              </span>
            }
          >
            <CoverageFileTable files={coverage.files} />
          </ContentSection>
        )}
      </div>
    );
  }

  const tests = readTests(payload);
  const scalars = readScalars(payload);
  const metrics: Metric[] = scalars.map((s) => ({ label: s.label, value: s.value }));

  if (tests) {
    const total = tests.passed + tests.failed;
    return (
      <div className="flex flex-col gap-4">
        <StatusInline
          total={`${total} test${total === 1 ? "" : "s"}`}
          segments={[
            { status: "completed", count: tests.passed, label: "passed" },
            { status: "failed", count: tests.failed, label: "failed" },
          ]}
        />
        {metrics.length > 0 && <MetricTable metrics={metrics} />}
      </div>
    );
  }

  if (metrics.length === 0) {
    return (
      <EmptyState title="Nothing readable in this snapshot" density="compact" />
    );
  }

  return <MetricTable metrics={metrics} />;
}
