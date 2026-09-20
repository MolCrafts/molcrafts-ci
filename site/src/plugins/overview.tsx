import { ContentSection } from "@/components/blocks/content-section";
import { WorkSurface } from "@/components/layout/WorkSurface";
import { MetaStrip, type MetaFact } from "@/components/meta-strip";
import { BandSkeleton } from "@/components/skeletons";
import type { SnapshotStatus } from "@/components/snapshot-status";
import { StatusInline, type StatusSegment } from "@/components/status-inline";
import { StreamTrends } from "@/components/stream-trends";
import { EmptyState } from "@/components/ui/empty-state";
import { useProjectStreams } from "@/lib/project-streams";
import { relativeTime, shortCommit } from "@/lib/snapshot-data";
import { STATUS_ORDER } from "@/lib/stream-summary";
import { pluginForKind } from "@/plugins/registry";
import type { KindTabPanelProps, KindTabPlugin } from "@/plugins/types";

const STATUS_ROLLUP_LABEL: Partial<Record<SnapshotStatus, string>> = {
  failed: "failing",
  warning: "attention",
  completed: "passing",
  ready: "no verdict",
  draft: "empty",
};

/**
 * Project overview — situation and next step.
 *
 * Answers three questions and no more: is this project green, which stream
 * moved, and what do I open next. Identity lives in the navigator and the
 * breadcrumb, provenance in the inspector, and the full per-kind inventory in
 * that kind's own tab.
 */
export function OverviewPanel({ project, openTab }: KindTabPanelProps) {
  const { streams, error } = useProjectStreams();

  if (error) {
    return (
      <div className="p-4">
        <EmptyState title="Failed to read this project's indexes" description={error} />
      </div>
    );
  }

  const current = streams?.find((s) => s.entry)?.entry ?? null;
  const facts: MetaFact[] = current
    ? [
        { label: "Repository", value: current.repository ?? project.id, mono: true },
        { label: "Ref", value: current.ref ?? "—", mono: true },
        { label: "Commit", value: shortCommit(current.commit), mono: true },
        { label: "Profile", value: current.profile ?? "—", mono: true },
        {
          label: "Workflow run",
          value: current.workflow_run != null ? `#${current.workflow_run}` : "—",
          mono: true,
        },
        { label: "Published", value: relativeTime(current.timestamp), mono: true },
      ]
    : [];

  const segments: StatusSegment[] = STATUS_ORDER.flatMap((status) => {
    const count = streams?.filter((s) => s.status === status).length ?? 0;
    if (!count) return [];
    return [{ status, count, label: STATUS_ROLLUP_LABEL[status] ?? status }];
  });

  return (
    <WorkSurface>
      {streams === null ? <BandSkeleton /> : facts.length > 0 ? <MetaStrip facts={facts} /> : null}

      {streams !== null && segments.length > 0 && (
        <StatusInline
          total={`${streams.length} stream${streams.length === 1 ? "" : "s"}`}
          segments={segments}
        />
      )}

      {/* No count here: the StatusInline above already states how many
          streams there are, and a second copy just trains the eye to skip. */}
      <ContentSection title="History">
        <StreamTrends
          streams={streams}
          /* Navigation only: a stream is not a snapshot, so this does not
             open the inspector. Picking a generation over there does. */
          onOpen={(stream) => {
            const tabId = pluginForKind(project.id, stream.kind)?.id;
            if (tabId && openTab) openTab(tabId);
          }}
          emptyTitle="Nothing published for this project yet"
          emptyDescription={`No index under data/index/${project.id}/.`}
        />
      </ContentSection>
    </WorkSurface>
  );
}

export const overviewPlugin: KindTabPlugin = {
  id: "overview",
  label: "Overview",
  order: 0,
  available: () => true,
  Component: OverviewPanel,
};
