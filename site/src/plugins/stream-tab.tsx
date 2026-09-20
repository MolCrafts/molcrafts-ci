import { useEffect, useState } from "react";

import { ContentSection } from "@/components/blocks/content-section";
import { WorkSurface } from "@/components/layout/WorkSurface";
import { PayloadView } from "@/components/payload-view";
import { SnapshotTable } from "@/components/snapshot-table";
import { EmptyState } from "@/components/ui/empty-state";
import { useSelect } from "@/lib/selection";
import {
  fetchKindEntries,
  fetchSnapshot,
  newestFirst,
  resolveKind,
  type IndexEntry,
  type Snapshot,
} from "@/lib/snapshot-data";
import { kindMatches, type StreamKind } from "./stream-kinds";
import type { KindTabPanelProps, KindTabPlugin, ProjectContext } from "./types";

/**
 * One stream's detail tab.
 *
 * Every kind gets the same two answers in the same order: what the current
 * generation says, and what else has been published. The reading of the payload
 * is `PayloadView`'s, keyed on shape — so a kind needs no tab of its own unless
 * it earns one.
 *
 * There is no separate generation picker: the table below *is* the picker, and
 * two controls for one action is the duplication a tab strip already taught us
 * to delete. Provenance is absent too — the inspector owns it.
 */
export function makeStreamTab(opts: StreamKind): KindTabPlugin {
  function StreamTab({ project }: KindTabPanelProps) {
    const kind = resolveKind(project.kinds, opts.aliases);
    const [entries, setEntries] = useState<IndexEntry[] | null>(null);
    const [activeId, setActiveId] = useState<string | null>(null);
    const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
    const [snapshotSettled, setSnapshotSettled] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const select = useSelect();

    useEffect(() => {
      if (!kind) {
        setEntries([]);
        return;
      }
      let cancelled = false;
      setEntries(null);
      setError(null);
      fetchKindEntries(project.id, kind)
        .then((rows) => {
          if (cancelled) return;
          const sorted = newestFirst(rows);
          setEntries(sorted);
          setActiveId(sorted[0]?.snapshot_id ?? null);
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : String(err));
            setEntries([]);
          }
        });
      return () => {
        cancelled = true;
      };
    }, [project.id, kind]);

    useEffect(() => {
      const entry = entries?.find((e) => e.snapshot_id === activeId);
      if (!entry) {
        setSnapshot(null);
        setSnapshotSettled(entries !== null);
        return;
      }
      let cancelled = false;
      setSnapshotSettled(false);
      fetchSnapshot(entry).then((snap) => {
        if (cancelled) return;
        setSnapshot(snap);
        setSnapshotSettled(true);
      });
      return () => {
        cancelled = true;
      };
    }, [entries, activeId]);

    if (!kind) {
      return (
        <div className="p-4">
          <EmptyState
            title={`No ${opts.label} index`}
            description={`${project.id} publishes none of: ${opts.aliases.join(", ")}.`}
            density="compact"
          />
        </div>
      );
    }

    if (error) {
      return (
        <div className="p-4">
          <EmptyState title="Failed to load index" description={error} density="compact" />
        </div>
      );
    }

    const hasEntries = entries === null || entries.length > 0;

    return (
      <WorkSurface>
        {hasEntries && (
          <PayloadView
            payload={snapshot?.payload ?? null}
            loading={entries === null}
            settled={snapshotSettled}
          />
        )}

        <ContentSection
          title="Generations"
          action={
            entries && (
              <span className="font-mono text-label tabular-nums text-muted-foreground">
                {entries.length}
              </span>
            )
          }
        >
          <SnapshotTable
            entries={entries}
            selectedId={activeId}
            onSelect={(snapshotId) => {
              setActiveId(snapshotId);
              // An explicit pick is what opens the inspector. The body comes
              // from there, so the click does not wait on a fetch.
              const entry = entries?.find((e) => e.snapshot_id === snapshotId);
              if (entry) select({ stream: kind ?? entry.kind ?? "", entry, snapshot: null });
            }}
            emptyTitle={`No ${opts.label} snapshots`}
            emptyDescription={`data/index/${project.id}/${kind}.jsonl is empty or missing.`}
          />
        </ContentSection>
      </WorkSurface>
    );
  }

  return {
    id: opts.id,
    label: opts.label,
    order: opts.order,
    available: (ctx: ProjectContext) => kindMatches(ctx.kinds, opts.aliases),
    Component: StreamTab,
  };
}
