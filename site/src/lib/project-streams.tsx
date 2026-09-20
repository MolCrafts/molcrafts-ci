import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchKindEntries, fetchSnapshot, newestFirst } from "@/lib/snapshot-data";
import { STATUS_ORDER, summarise, type StreamSummary } from "@/lib/stream-summary";
import type { ProjectContext } from "@/plugins/types";

export interface ProjectStreamsState {
  /** null while the project's indexes are still being read. */
  streams: StreamSummary[] | null;
  error: string | null;
}

const ProjectStreamsContext = createContext<ProjectStreamsState>({
  streams: null,
  error: null,
});

/**
 * How many generations the overview charts.
 *
 * One request per generation per stream, so this is a real cost on a project
 * with a long history. Twelve is the sparkline's point count and enough to see
 * a direction.
 */
const HISTORY_DEPTH = 12;

async function loadStreams(project: ProjectContext): Promise<StreamSummary[]> {
  const summaries = await Promise.all(
    project.kinds.map(async (kind) => {
      const entries = newestFirst(await fetchKindEntries(project.id, kind));
      const bodies = await Promise.all(
        entries.slice(0, HISTORY_DEPTH).map(async (entry) => ({
          entry,
          snapshot: await fetchSnapshot(entry),
        })),
      );
      return summarise(kind, entries, bodies);
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
 * same set of streams. Fetching once here is what keeps them from disagreeing —
 * and keeps three surfaces from issuing the same requests.
 */
export function ProjectStreamsProvider({
  project,
  children,
}: {
  project: ProjectContext | null;
  children: ReactNode;
}) {
  const [streams, setStreams] = useState<StreamSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const projectId = project?.id ?? null;
  const kindKey = project?.kinds.join(",") ?? "";

  useEffect(() => {
    if (!project) {
      setStreams([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setStreams(null);
    setError(null);
    loadStreams(project)
      .then((next) => {
        if (!cancelled) setStreams(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setStreams([]);
        }
      });
    return () => {
      cancelled = true;
    };
    // Keyed on id + kind set rather than on `project`: the object identity
    // changes on every parent render, but only those two decide which files
    // to read, and re-running on identity alone would refetch continuously.
  }, [projectId, kindKey]);

  const value = useMemo(() => ({ streams, error }), [streams, error]);

  return (
    <ProjectStreamsContext.Provider value={value}>{children}</ProjectStreamsContext.Provider>
  );
}

export const useProjectStreams = (): ProjectStreamsState => useContext(ProjectStreamsContext);
