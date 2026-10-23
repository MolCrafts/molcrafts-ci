import { useEffect, useMemo, useState } from "react";

import { OperationsDock } from "@/components/operations-dock";
import { ProfileSelect } from "@/components/profile-select";
import {
  EmptyState,
  ExplorerPanel,
  NavList,
  NavListItem,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  ThemeToggle,
  WorkbenchHeader,
  WorkbenchShell,
} from "@molcrafts/ui";
import { loadIndexListing, projectsFromListing } from "@/lib/index-data";
import { ProjectRecordsProvider } from "@/lib/project-records";
import { useProjectRecords } from "@/lib/project-records";
import { useThemePreference } from "@/lib/theme-preference";
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
      <Workbench
        projects={projects}
        loadError={loadError}
        selected={selected}
        url={url}
        setUrl={setUrl}
      />
    </ProjectRecordsProvider>
  );
}

/**
 * Everything inside the project-records provider.
 *
 * URL state owns project/tab/snapshot. Provenance for the open generation
 * lives on the record tab header — there is no side inspector.
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
  const { profiles } = useProjectRecords();
  const [theme, setTheme] = useThemePreference();

  const tabs = selected ? pluginsFor(selected) : [];
  // A tab named in the address that this project does not have falls back to
  // the first, so a stale link never lands on an empty surface.
  const activeTab =
    url.tab && tabs.some((t) => t.id === url.tab) ? url.tab : (tabs[0]?.id ?? null);
  const activeLabel = tabs.find((t) => t.id === activeTab)?.label ?? null;

  return (
    <WorkbenchShell
      storageKey="molci"
      labels={{ navigator: "Projects", main: "CI records", dock: "Operations" }}
      header={
        <WorkbenchHeader
          /* The product name is the document's only h1. */
          title={
            <>
              <span className="font-normal text-muted-foreground">MolCrafts</span> CI
            </>
          }
          breadcrumb={selected ? [selected.id, ...(activeLabel ? [activeLabel] : [])] : []}
          actions={
            <>
              <ProfileSelect
                profiles={profiles}
                value={selected ? (url.profile ?? profiles[0] ?? null) : null}
                onChange={(profile) => setUrl({ profile })}
              />
              <ThemeToggle theme={theme} onThemeChange={setTheme} />
            </>
          }
        />
      }
      navigator={
        <ExplorerPanel title="Projects">
          {projects === null ? (
            <EmptyState title="Loading projects…" density="inline" />
          ) : loadError ? (
            <EmptyState title="Failed to load index" description={loadError} />
          ) : projects.length === 0 ? (
            <EmptyState title="No projects yet" />
          ) : (
            /* Flat: the tabs already are the record navigation, and counts or
               status belong to the surface the selection opens. */
            <NavList>
              {projects.map((project) => (
                <NavListItem
                  key={project.id}
                  current={project.id === selected?.id}
                  onClick={() => setUrl({ project: project.id, tab: null })}
                >
                  {project.id}
                </NavListItem>
              ))}
            </NavList>
          )}
        </ExplorerPanel>
      }
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
