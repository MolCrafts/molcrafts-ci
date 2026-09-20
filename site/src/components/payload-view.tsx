import type { JSX } from "react";

import { ContentSection } from "@/components/blocks/content-section";
import {
  COVERAGE_FILE_LIMIT,
  CoverageFileTable,
  coverageTone,
  formatPercent,
  uncoveredCount,
} from "@/components/coverage-file-table";
import { MeasureBand, type Measure } from "@/components/meta-strip";
import { MetricTable, type Metric } from "@/components/metric-table";
import { BandSkeleton } from "@/components/skeletons";
import { StatusInline } from "@/components/status-inline";
import { EmptyState } from "@/components/ui/empty-state";
import { RunLink } from "@/components/run-link";
import { readCoverage, readScalars, readTests } from "@/lib/payload";
import type { IndexEntry } from "@/lib/snapshot-data";

export interface PayloadViewProps {
  /** The selected snapshot's body; null while loading or when unreadable. */
  payload: unknown;
  loading?: boolean;
  /** True once the fetch settled, so null means unreadable rather than pending. */
  settled?: boolean;
  /** The entry this body came from, so detail can point at the CI run. */
  entry?: IndexEntry | null;
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
  entry = null,
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
    // Only what the producer actually measured. coverage.py reports no
    // function coverage and llvm-cov no branches by default, and rendering
    // those as full-weight cells reading "—" filled half the primary fold
    // with absence.
    const measures: Measure[] = (
      [
        ["Lines", coverage.totals.lines],
        ["Branches", coverage.totals.branches],
        ["Functions", coverage.totals.functions],
        ["Statements", coverage.totals.statements],
      ] as const
    )
      .filter(([, value]) => value != null)
      .map(([label, value]) => ({
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
            title="Least covered"
            action={
              <span className="text-label text-muted-foreground">
                {coverage.files.filter((f) => uncoveredCount(f) > 0).length >
                COVERAGE_FILE_LIMIT ? (
                  <>
                    {COVERAGE_FILE_LIMIT} of {coverage.files.length} files ·{" "}
                    <RunLink repository={entry?.repository} run={entry?.workflow_run}>
                      full report
                    </RunLink>
                  </>
                ) : (
                  `${coverage.files.length} files`
                )}
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
    const total = tests.passed + tests.failed + tests.skipped;
    // `readScalars` returns the same counts StatusInline just stated, so the
    // metric table repeated passed/failed/skipped forty pixels below it. Only
    // scalars the line does not already carry survive.
    const consumed = new Set(["passed", "failed", "skipped", "errors", "failures"]);
    const extra = metrics.filter((m) => !consumed.has(m.label.toLowerCase()));

    return (
      <div className="flex flex-col gap-4">
        <StatusInline
          total={`${total} test${total === 1 ? "" : "s"}`}
          segments={[
            { status: "completed", count: tests.passed, label: "passed" },
            { status: "failed", count: tests.failed, label: "failed" },
            { status: "cancelled", count: tests.skipped, label: "skipped" },
          ]}
        />
        {extra.length > 0 && <MetricTable metrics={extra} />}
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
