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
import { EmptyState } from "@molcrafts/design";
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

    // Files with something left to test — the only ones the table lists.
    const withGaps = coverage.files.filter((f) => uncoveredCount(f) > 0).length;

    return (
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <MeasureBand measures={measures} />
        {coverage.files.length > 0 && (
          <ContentSection
            title="Files"
            action={
              <span className="text-label text-muted-foreground">
                {withGaps > COVERAGE_FILE_LIMIT ? (
                  <>
                    {COVERAGE_FILE_LIMIT} of {withGaps} ·{" "}
                    <RunLink repository={entry?.repository} run={entry?.workflow_run}>
                      all
                    </RunLink>
                  </>
                ) : (
                  withGaps
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
    const share = (n: number) => (total > 0 ? (100 * n) / total : 0);

    /*
     * The same band coverage gets, for the same reason.
     *
     * A suite result is one reading in three parts, exactly as coverage is one
     * reading in two — so it is read at the same size. A single thin line here
     * beside a full measure band there made the two record tabs look like
     * different products, and the counts are the whole of what this record
     * publishes.
     *
     * Zero is not absence. Coverage omits a total the producer did not
     * measure; `Failed 0` is measured, and it is the number a reader came for.
     */
    const measures: Measure[] = [
      { label: "Tests", value: String(total) },
      {
        label: "Passed",
        value: String(tests.passed),
        percent: share(tests.passed),
        tone: "bg-status-completed",
      },
      {
        label: "Failed",
        value: String(tests.failed),
        percent: share(tests.failed),
        tone: "bg-status-failed",
      },
      {
        label: "Skipped",
        value: String(tests.skipped),
        percent: share(tests.skipped),
        tone: "bg-status-cancelled",
      },
    ];

    // Whatever the producer published beyond the counts the band now states.
    const counted = new Set(["passed", "failed", "skipped", "errors", "failures", "tests"]);
    const extra = metrics.filter((m) => !counted.has(m.label.toLowerCase()));

    return (
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <MeasureBand measures={measures} />
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
