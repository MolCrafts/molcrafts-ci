import { useEffect, useState } from "react";

import { WorkSurface } from "@/components/layout/WorkSurface";
import { PayloadView } from "@/components/payload-view";
import { SnapshotTable } from "@/components/snapshot-table";
import { EmptyState } from "@/components/ui/empty-state";
import { useSelect } from "@/lib/selection";
import { useUrlState } from "@/lib/use-url-state";
import {
  fetchRecordEntries,
  fetchSnapshot,
  newestFirst,
  resolveRecord,
  type IndexEntry,
  type Snapshot,
} from "@/lib/snapshot-data";
import { recordMatches, type RecordDescriptor } from "./records";
import type { RecordTabPanelProps, RecordTabPlugin, ProjectContext } from "./types";

/**
 * One record's detail tab.
 *
 * Every record gets the same two answers in the same order: what the current
 * generation says, and what else has been published. The reading of the payload
 * is `PayloadView`'s, keyed on shape — so a record needs no tab of its own unless
 * it earns one.
 *
 * There is no separate generation picker: the table below *is* the picker, and
 * two controls for one action is the duplication a tab strip already taught us
 * to delete. Provenance is absent too — the inspector owns it.
 */
export function makeRecordTab(opts: RecordDescriptor): RecordTabPlugin {
  function RecordTab({ project }: RecordTabPanelProps) {
    const record = resolveRecord(project.records, opts.aliases);
    const [entries, setEntries] = useState<IndexEntry[] | null>(null);
    const [activeId, setActiveId] = useState<string | null>(null);
    const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
    const [snapshotSettled, setSnapshotSettled] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const select = useSelect();
    const [url, setUrl] = useUrlState();

    useEffect(() => {
      if (!record) {
        setEntries([]);
        return;
      }
      let cancelled = false;
      setEntries(null);
      setError(null);
      fetchRecordEntries(project.id, record)
        .then((rows) => {
          if (cancelled) return;
          const sorted = newestFirst(rows);
          setEntries(sorted);
          // A shared link names a generation; a bare visit gets the newest.
          const named = url.snapshot && sorted.find((e) => e.snapshot_id === url.snapshot);
          setActiveId((named ? named.snapshot_id : sorted[0]?.snapshot_id) ?? null);
          if (named) select({ record: record ?? named.record ?? "", entry: named, snapshot: null });
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
    }, [project.id, record]);

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

    if (!record) {
      return (
        <div className="p-4">
          <EmptyState title={`No ${opts.label} published`} density="compact" />
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

        <SnapshotTable
          entries={entries}
          selectedId={activeId}
          onSelect={(snapshotId) => {
            setActiveId(snapshotId);
            // An explicit pick is what opens the inspector, and what the
            // address records so the view can be shared. The body is fetched
            // there, so the click does not wait on it.
            const entry = entries?.find((e) => e.snapshot_id === snapshotId);
            if (entry) select({ record: record ?? entry.record ?? "", entry, snapshot: null });
            setUrl({ snapshot: snapshotId });
          }}
          emptyTitle={`No ${opts.label} snapshots`}
        />
      </WorkSurface>
    );
  }

  return {
    id: opts.id,
    label: opts.label,
    order: opts.order,
    available: (ctx: ProjectContext) => recordMatches(ctx.records, opts.aliases),
    Component: RecordTab,
  };
}
