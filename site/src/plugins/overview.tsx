import { WorkSurface } from "@/components/layout/WorkSurface";
import { RecordTrends } from "@/components/record-trends";
import { EmptyState } from "@/components/ui/empty-state";
import { useProjectRecords } from "@/lib/project-records";
import { pluginForRecord } from "@/plugins/registry";
import type { RecordTabPanelProps, RecordTabPlugin } from "@/plugins/types";

/**
 * Project overview — one chart per record, and nothing else.
 *
 * What was here before said the same things twice: a MetaStrip repeating facts
 * the tiles carry per record, and a rollup counting rows that were all on
 * screen anyway. The strip was also wrong — it read the commit off whichever
 * record happened to sort first, which is not the project's commit, because
 * records sit at different commits by nature.
 */
export function OverviewPanel({ project, openTab }: RecordTabPanelProps) {
  const { records, error } = useProjectRecords();

  if (error) {
    return (
      <div className="p-4">
        <EmptyState title="Cannot read this project" description={error} />
      </div>
    );
  }

  return (
    <WorkSurface>
      <RecordTrends
        records={records}
        onOpen={(record) => {
          const tabId = pluginForRecord(project.id, record.record)?.id;
          if (tabId && openTab) openTab(tabId);
        }}
        emptyTitle="Nothing published yet"
      />
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
