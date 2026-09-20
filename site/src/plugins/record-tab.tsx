import { useEffect, useState } from "react";

import { CommitLink } from "@/components/commit-link";
import { HistorySelect } from "@/components/history-select";
import { WorkSurface } from "@/components/layout/WorkSurface";
import { PayloadView } from "@/components/payload-view";
import { RunLink } from "@/components/run-link";
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
 * This tab answers exactly one question: what does *this* generation say. The
 * reading of the payload is `PayloadView`'s, keyed on shape — so a record needs
 * no tab of its own unless it earns one.
 *
 * The full history is not here. It lives on the overview, where it is a series
 * with a direction rather than a list of identifiers, and the picker here only
 * has to reach the recent past. That split is what lets this fold be one
 * reading instead of a table competing with it.
 *
 * The header carries where this generation came from — commit and CI run — so
 * the detail this site deliberately does not render is one click away.
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
    const active = entries?.find((e) => e.snapshot_id === activeId) ?? null;

    return (
      <WorkSurface>
        {!hasEntries ? (
          <EmptyState title={`No ${opts.label} snapshots`} density="compact" />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border pb-3">
              <HistorySelect
                entries={entries}
                selectedId={activeId}
                onSelect={(snapshotId) => {
                  setActiveId(snapshotId);
                  // An explicit pick is what points the inspector, and what the
                  // address records so the view can be shared. The body is
                  // fetched there, so the pick does not wait on it.
                  const entry = entries?.find((e) => e.snapshot_id === snapshotId);
                  if (entry) {
                    select({ record: record ?? entry.record ?? "", entry, snapshot: null });
                  }
                  setUrl({ snapshot: snapshotId });
                }}
              />
              {active && (
                <span className="flex items-center gap-x-3 text-label text-muted-foreground">
                  <CommitLink repository={active.repository} commit={active.commit} />
                  <RunLink repository={active.repository} run={active.workflow_run}>
                    run
                  </RunLink>
                </span>
              )}
            </div>

            <PayloadView
              payload={snapshot?.payload ?? null}
              loading={entries === null}
              settled={snapshotSettled}
              entry={active}
            />
          </>
        )}
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
