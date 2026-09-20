import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchRecordEntries, fetchSnapshot, newestFirst } from "@/lib/snapshot-data";
import { STATUS_ORDER, summarise, type RecordSummary } from "@/lib/record-summary";
import type { ProjectContext } from "@/plugins/types";

export interface ProjectRecordsState {
  /** null while the project's indexes are still being read. */
  records: RecordSummary[] | null;
  /** Union of every profile the project publishes under, sorted. */
  profiles: string[];
  error: string | null;
}

const ProjectRecordsContext = createContext<ProjectRecordsState>({
  records: null,
  profiles: [],
  error: null,
});

/**
 * How many generations the overview charts.
 *
 * One request per generation per record, so this is a real cost on a project
 * with a long history. Twelve is the sparkline's point count and enough to see
 * a direction.
 */
const HISTORY_DEPTH = 12;

async function loadRecords(
  project: ProjectContext,
  preferredProfile: string | null,
): Promise<RecordSummary[]> {
  const summaries = await Promise.all(
    project.records.map(async (record) => {
      const entries = newestFirst(await fetchRecordEntries(project.id, record));
      const bodies = await Promise.all(
        entries.slice(0, HISTORY_DEPTH).map(async (entry) => ({
          entry,
          snapshot: await fetchSnapshot(entry),
        })),
      );
      return summarise(record, entries, bodies, preferredProfile);
    }),
  );
  return summaries.sort(
    (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status),
  );
}

/**
 * One reader of a project's indexes, for the whole shell.
 *
 * The overview table, the problems tab and the publish log all describe the
 * same set of records. Fetching once here is what keeps them from disagreeing —
 * and keeps three surfaces from issuing the same requests.
 */
export function ProjectRecordsProvider({
  project,
  profile,
  children,
}: {
  project: ProjectContext | null;
  /** Project-wide profile choice; records that lack it fall back per record. */
  profile: string | null;
  children: ReactNode;
}) {
  const [records, setRecords] = useState<RecordSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const projectId = project?.id ?? null;
  const recordKey = project?.records.join(",") ?? "";

  useEffect(() => {
    if (!project) {
      setRecords([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setRecords(null);
    setError(null);
    loadRecords(project, profile)
      .then((next) => {
        if (!cancelled) setRecords(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setRecords([]);
        }
      });
    return () => {
      cancelled = true;
    };
    // Keyed on id + record set rather than on `project`: the object identity
    // changes on every parent render, but only those two decide which files
    // to read, and re-running on identity alone would refetch continuously.
  }, [projectId, recordKey, profile]);

  const profiles = useMemo(
    () => [...new Set((records ?? []).flatMap((s) => s.profiles))].sort(),
    [records],
  );

  const value = useMemo(() => ({ records, profiles, error }), [records, profiles, error]);

  return (
    <ProjectRecordsContext.Provider value={value}>{children}</ProjectRecordsContext.Provider>
  );
}

export const useProjectRecords = (): ProjectRecordsState => useContext(ProjectRecordsContext);
