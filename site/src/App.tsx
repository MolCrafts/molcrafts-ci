import { useEffect, useMemo, useState } from "react";

import { LeftExplorer } from "@/components/layout/ExplorerShell";
import { WorkbenchShell } from "@/components/layout/WorkbenchShell";
import { OperationsDock } from "@/components/operations-dock";
import { ProjectList } from "@/components/project-list";
import { SnapshotInspector } from "@/components/snapshot-inspector";
import { ThemeToggle } from "@/components/theme-toggle";
import { EmptyState } from "@/components/ui/empty-state";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { loadIndexListing, projectsFromListing } from "@/lib/index-data";
import { ProjectStreamsProvider } from "@/lib/project-streams";
import { SelectionProvider, useSelection } from "@/lib/selection";
import { pluginsFor } from "@/plugins/registry";
import type { ProjectContext } from "@/plugins/types";

export function App() {
  const [projects, setProjects] = useState<ProjectContext[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadIndexListing()
      .then((listing) => {
        if (cancelled) return;
        const next = projectsFromListing(listing);
        setProjects(next);
        setSelectedId((prev) => {
          if (prev && next.some((p) => p.id === prev)) return prev;
          return next[0]?.id ?? null;
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
          setProjects([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => projects?.find((p) => p.id === selectedId) ?? null,
    [projects, selectedId],
  );

  return (
    <ProjectStreamsProvider project={selected}>
      <SelectionProvider resetKey={selected?.id ?? null}>
        <Workbench
          projects={projects}
          loadError={loadError}
          selected={selected}
          selectedId={selectedId}
          onSelectProject={setSelectedId}
        />
      </SelectionProvider>
    </ProjectStreamsProvider>
  );
}

/**
 * Everything inside the providers.
 *
 * The shell needs to know whether anything is selected — that is what decides
 * whether the inspector column exists at all — and only a child of
 * `SelectionProvider` can answer that.
 */
function Workbench({
  projects,
  loadError,
  selected,
  selectedId,
  onSelectProject,
}: {
  projects: ProjectContext[] | null;
  loadError: string | null;
  selected: ProjectContext | null;
  selectedId: string | null;
  onSelectProject: (id: string) => void;
}) {
  const selection = useSelection();
  const [requestedTab, setRequestedTab] = useState<string | null>(null);

  const tabs = selected ? pluginsFor(selected) : [];
  // A requested tab that this project does not have falls back to the first,
  // so switching projects never lands on an empty surface.
  const activeTab =
    requestedTab && tabs.some((t) => t.id === requestedTab) ? requestedTab : (tabs[0]?.id ?? null);
  const activeLabel = tabs.find((t) => t.id === activeTab)?.label ?? null;

  return (
    <WorkbenchShell
      header={
        /* Identity once, then the breadcrumb and nothing else. */
        <header className="flex h-header shrink-0 items-center gap-3 border-b border-border bg-surface px-4">
          <p className="shrink-0 text-title font-semibold tracking-tight">
            <span className="font-medium text-muted-foreground">MolCrafts</span> CI
          </p>
          {selected && (
            <>
              <Separator orientation="vertical" className="h-5" />
              <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2">
                <span className="truncate text-body text-muted-foreground">{selected.id}</span>
                {activeLabel && (
                  <>
                    <span aria-hidden="true" className="text-border-strong">
                      /
                    </span>
                    <span className="truncate text-body font-medium">{activeLabel}</span>
                  </>
                )}
              </nav>
            </>
          )}
          {/* Breadcrumb left, the surface's verbs right. Nothing else. */}
          <span className="flex-1" />
          <ThemeToggle />
        </header>
      }
      navigator={
        /* The vendored block defaults to the canvas colour; the navigator
           is chrome, so it takes the surface step above it. */
        <LeftExplorer title="Projects" className="bg-surface">
          {projects === null ? (
            <EmptyState title="Loading projects…" density="inline" />
          ) : loadError ? (
            <EmptyState title="Failed to load index" description={loadError} density="compact" />
          ) : projects.length === 0 ? (
            <EmptyState
              title="No projects yet"
              description="Tracked snapshots appear here after ingest and publish."
              density="compact"
            />
          ) : (
            <ProjectList
              projects={projects}
              selectedId={selectedId}
              onSelect={onSelectProject}
            />
          )}
        </LeftExplorer>
      }
      inspector={selection ? <SnapshotInspector /> : null}
      dock={<OperationsDock />}
    >
      {!selected ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <EmptyState
            title="Select a project"
            description="Choose a project from the left to open its snapshot streams."
          />
        </div>
      ) : tabs.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <EmptyState
            title="No published streams"
            description={`Nothing under data/index/${selected.id}/ yet.`}
          />
        </div>
      ) : (
        <Tabs
          value={activeTab ?? undefined}
          onValueChange={setRequestedTab}
          className="flex min-h-0 flex-1 gap-0"
        >
          <div className="shrink-0 border-b border-border bg-surface px-3 pt-2">
            <TabsList variant="line" className="w-full justify-start">
              {tabs.map((plugin) => (
                <TabsTrigger key={plugin.id} value={plugin.id}>
                  {plugin.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {tabs.map((plugin) => {
            const Panel = plugin.Component;
            return (
              <TabsContent
                key={plugin.id}
                value={plugin.id}
                className="mt-0 flex min-h-0 flex-1 flex-col outline-none"
              >
                <Panel project={selected} openTab={setRequestedTab} />
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </WorkbenchShell>
  );
}
