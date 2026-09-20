import type { JSX } from "react";

import { ContentSection } from "@/components/blocks/content-section";
import { WorkSurface } from "@/components/layout/WorkSurface";
import { MetaStrip, type MetaFact } from "@/components/meta-strip";
import { RecordTable } from "@/components/record-table";
import { RecordTrends } from "@/components/record-trends";
import { StatusInline, type StatusSegment } from "@/components/status-inline";
import { EmptyState } from "@/components/ui/empty-state";
import { useProjectRecords } from "@/lib/project-records";
import { relativeTime } from "@/lib/snapshot-data";
import type { RecordSummary } from "@/lib/record-summary";
import { pluginForRecord } from "@/plugins/registry";
import type { RecordTabPanelProps, RecordTabPlugin } from "@/plugins/types";

/**
 * Facts that are true of the *project*, not of one of its records.
 *
 * The strip this replaces read the commit off whichever record sorted first,
 * which is not the project's commit — records are published by separate CI
 * runs and sit at different commits by nature. Commit and run therefore live
 * in the table, per row. What survives here is what genuinely aggregates:
 * how many records, how much history, and when the project last published
 * anything at all.
 */
function projectFacts(records: RecordSummary[]): MetaFact[] {
  const snapshots = records.reduce((n, r) => n + r.entries.length, 0);
  const latest = records
    .map((r) => r.entry?.timestamp)
    .filter((t): t is string => Boolean(t))
    .sort()
    .at(-1);
  const profiles = [...new Set(records.flatMap((r) => r.profiles))];

  const facts: MetaFact[] = [
    { label: "Records", value: records.length, mono: true },
    { label: "Snapshots", value: snapshots, mono: true },
    { label: "Last published", value: relativeTime(latest) },
  ];
  if (profiles.length === 1) {
    facts.push({ label: "Profile", value: profiles[0], mono: true });
  } else if (profiles.length > 1) {
    facts.push({ label: "Profiles", value: profiles.length, mono: true });
  }
  return facts;
}

/** Where to look next, as a distribution over record verdicts. */
function verdictSegments(records: RecordSummary[]): StatusSegment[] {
  const counts = new Map<RecordSummary["status"], number>();
  for (const r of records) counts.set(r.status, (counts.get(r.status) ?? 0) + 1);
  return [...counts.entries()].map(([status, count]) => ({
    status,
    count,
    label: status,
  }));
}

/**
 * Project overview — the situation above, the history below.
 *
 * Two jobs, in that order. The top answers "what is the state of this project
 * and what do I open next": a strip of facts that aggregate, a distribution
 * that says where to look, and the record inventory carrying each record's
 * current reading. The bottom answers "how did it get here" as one chart per
 * record — passes, percentages and nanoseconds share no axis, so a single plot
 * would invent a relationship the data does not have.
 *
 * The complete generation history of each record is reachable from here rather
 * than from the record tabs, which read one generation at a time.
 */
export function OverviewPanel({ project, openTab }: RecordTabPanelProps): JSX.Element {
  const { records, error } = useProjectRecords();

  if (error) {
    return (
      <div className="p-4">
        <EmptyState title="Cannot read this project" description={error} />
      </div>
    );
  }

  const open = (record: RecordSummary) => {
    const tabId = pluginForRecord(project.id, record.record)?.id;
    if (tabId && openTab) openTab(tabId);
  };

  return (
    <WorkSurface>
      {records !== null && records.length > 0 && (
        <>
          <MetaStrip facts={projectFacts(records)} />
          <StatusInline
            total={`${records.length} record${records.length === 1 ? "" : "s"}`}
            segments={verdictSegments(records)}
          />
        </>
      )}

      <RecordTable records={records} onOpen={open} emptyTitle="Nothing published yet" />

      {records !== null && records.length > 0 && (
        <ContentSection title="History">
          <RecordTrends records={records} onOpen={open} emptyTitle="Nothing published yet" />
        </ContentSection>
      )}
    </WorkSurface>
  );
}

export const overviewPlugin: RecordTabPlugin = {
  id: "overview",
  label: "Overview",
  order: 0,
  available: () => true,
  Component: OverviewPanel,
};
