import { useEffect, useMemo, useState } from "react";

import { LeftExplorer } from "@/components/layout/ExplorerShell";
import { WorkbenchShell } from "@/components/layout/WorkbenchShell";
import { OperationsDock } from "@/components/operations-dock";
import { ProfileSelect } from "@/components/profile-select";
import { ProjectList } from "@/components/project-list";
import { SnapshotInspector } from "@/components/snapshot-inspector";
import { ThemeToggle } from "@/components/theme-toggle";
import { EmptyState } from "@/components/ui/empty-state";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { loadIndexListing, projectsFromListing } from "@/lib/index-data";
import { ProjectRecordsProvider } from "@/lib/project-records";
import { useProjectRecords } from "@/lib/project-records";
import { SelectionProvider, useSelection } from "@/lib/selection";
import { useUrlState, type UrlPatch } from "@/lib/use-url-state";
import type { UrlState } from "@/lib/url-state";
import { pluginsFor } from "@/plugins/registry";
import type { ProjectContext } from "@/plugins/types";

export function App() {
  const [projects, setProjects] = useState<ProjectContext[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [url, setUrl] = useUrlState();

  useEffect(() => {
    let cancelled = false;
    loadIndexListing()
      .then((listing) => {
        if (cancelled) return;
        const next = projectsFromListing(listing);
        setProjects(next);
        // A shared link names its project; only a bare visit picks the first.
        setUrl((current) =>
          current.project && next.some((p) => p.id === current.project)
            ? {}
            : { project: next[0]?.id ?? null },
        );
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
    () => projects?.find((p) => p.id === url.project) ?? null,
    [projects, url.project],
  );

  return (
    <ProjectRecordsProvider project={selected} profile={url.profile}>
      <SelectionProvider resetKey={selected?.id ?? null}>
        <Workbench
          projects={projects}
          loadError={loadError}
          selected={selected}
          url={url}
          setUrl={setUrl}
        />
      </SelectionProvider>
    </ProjectRecordsProvider>
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
  url,
  setUrl,
}: {
  projects: ProjectContext[] | null;
  loadError: string | null;
  selected: ProjectContext | null;
  url: UrlState;
  setUrl: (patch: UrlPatch) => void;
}) {
  const selection = useSelection();
  const { profiles } = useProjectRecords();

  const tabs = selected ? pluginsFor(selected) : [];
  // A tab named in the address that this project does not have falls back to
  // the first, so a stale link never lands on an empty surface.
  const activeTab =
    url.tab && tabs.some((t) => t.id === url.tab) ? url.tab : (tabs[0]?.id ?? null);
  const activeLabel = tabs.find((t) => t.id === activeTab)?.label ?? null;

  return (
    <WorkbenchShell
      header={
        /* Identity once, then the breadcrumb and nothing else. */
        <header className="flex h-header shrink-0 items-center gap-3 border-b border-border bg-surface px-4">
          {/* The product name is the document's only h1. Without it the
              heading outline started at h2 (sections, navigator) and screen
              reader heading navigation had no top-level entry point. */}
          <h1 className="shrink-0 text-title font-semibold tracking-tight">
            <span className="font-medium text-muted-foreground">MolCrafts</span> CI
          </h1>
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
          <ProfileSelect
            profiles={profiles}
            value={selected ? (url.profile ?? profiles[0] ?? null) : null}
            onChange={(profile) => setUrl({ profile })}
          />
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
              density="compact"
            />
          ) : (
            <ProjectList
              projects={projects}
              selectedId={selected?.id ?? null}
              onSelect={(project) => setUrl({ project, tab: null })}
            />
          )}
        </LeftExplorer>
      }
      inspector={selection ? <SnapshotInspector /> : null}
      dock={<OperationsDock />}
    >
      {!selected ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <EmptyState title="Select a project" />
        </div>
      ) : tabs.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <EmptyState
            title={`Nothing published for ${selected.id}`}
          />
        </div>
      ) : (
        <Tabs
          value={activeTab ?? undefined}
          onValueChange={(tab) => setUrl({ tab })}
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
                <Panel project={selected} openTab={(tab) => setUrl({ tab })} />
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </WorkbenchShell>
  );
}
