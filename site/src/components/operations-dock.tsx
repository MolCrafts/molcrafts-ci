import { ChevronDownRegular as ChevronDown, ChevronUpRegular as ChevronUp } from "@fluentui/react-icons";
import { useState, type JSX, type ReactNode } from "react";

import { CommitLink } from "@/components/commit-link";
import {
  Badge,
  Button,
  EmptyState,
  RowsSkeleton,
  ScrollArea,
  StatusMark,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  useWorkbenchDock,
} from "@molcrafts/ui";
import { openRecord } from "@/lib/open-record";
import { useProjectRecords } from "@/lib/project-records";
import { useUrlState } from "@/lib/use-url-state";
import { relativeTime, type IndexEntry } from "@/lib/snapshot-data";
import type { RecordSummary } from "@/lib/record-summary";

type DockTab = "log" | "problems";

interface LogLine {
  record: RecordSummary;
  entry: IndexEntry;
}

/**
 * Live operations: what was published, and what is wrong.
 *
 * One region with tabs, never separate routes — a reader fixes a problem while
 * still looking at the record that reported it. Collapsing leaves the tab strip
 * in place so the counts stay readable.
 */
export function OperationsDock(): JSX.Element {
  const { records, error } = useProjectRecords();
  const { collapsed, toggle } = useWorkbenchDock();
  const [url, setUrl] = useUrlState();
  const [tab, setTab] = useState<DockTab>("log");

  const open = (record: string, snapshotId: string | undefined) => {
    if (!url.project) return;
    const patch = openRecord(url.project, record, snapshotId ?? null);
    if (patch) setUrl(patch);
  };

  const lines: LogLine[] = (records ?? [])
    .flatMap((record) => record.entries.map((entry) => ({ record, entry })))
    .sort((a, b) => (b.entry.timestamp ?? "").localeCompare(a.entry.timestamp ?? ""));

  // Failed suites, and records whose index could not be read.
  const problems = (records ?? []).filter((s) => s.status === "failed" || s.status === "warning");
  const problemCount = problems.length + (error ? 1 : 0);

  return (
    <Tabs value={tab} onValueChange={(next) => setTab(next as DockTab)} className="min-h-0 flex-1 gap-0">
      <div className="flex h-toolbar shrink-0 items-center gap-1 border-b border-border px-2">
        <TabsList className="h-full">
          <TabsTrigger value="log">
            Log
            {records && (
              <span className="text-label font-normal tabular-nums text-muted-foreground">{lines.length}</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="problems">
            Problems
            {problemCount > 0 && <Badge variant="destructive" className="tabular-nums">{problemCount}</Badge>}
          </TabsTrigger>
        </TabsList>
        <span className="flex-1" />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={collapsed ? "Expand panel" : "Collapse panel"}
          title={collapsed ? "Expand panel" : "Collapse panel"}
          aria-expanded={!collapsed}
          className="text-muted-foreground"
          onClick={toggle}
        >
          {collapsed ? <ChevronUp /> : <ChevronDown />}
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <TabsContent value="log">
          {records === null ? (
            <RowsSkeleton density="line" className="p-2" />
          ) : lines.length === 0 ? (
            <EmptyState title="Nothing published yet" density="inline" className="px-3 py-2" />
          ) : (
            <ul className="py-1">
              {lines.map(({ record, entry }, i) => (
                <DockRow
                  key={entry.snapshot_id ?? `${record.record}-${i}`}
                  lead={
                    <span className="shrink-0 text-label tabular-nums text-muted-foreground">
                      {entry.timestamp?.slice(0, 16).replace("T", " ") ?? "—"}
                    </span>
                  }
                  record={record.record}
                  onOpen={() => open(record.record, entry.snapshot_id)}
                >
                  gen {entry.generation ?? "—"} ·{" "}
                  <CommitLink repository={entry.repository} commit={entry.commit} /> ·{" "}
                  {entry.snapshot_id ?? entry.path ?? "—"}
                </DockRow>
              ))}
            </ul>
          )}
        </TabsContent>
        <TabsContent value="problems">
          {records === null ? (
            <RowsSkeleton density="line" className="p-2" />
          ) : problemCount === 0 ? (
            <EmptyState title="No problems" density="inline" className="px-3 py-2" />
          ) : (
            <ul className="py-1">
              {error && (
                <li className="flex min-h-8 items-center gap-3 px-3">
                  <StatusMark status="failed" />
                  <span className="truncate font-mono text-label text-foreground">{error}</span>
                </li>
              )}
              {problems.map((record) => (
                <DockRow
                  key={record.record}
                  lead={<StatusMark status={record.status} className="self-center" />}
                  record={record.record}
                  onOpen={() => open(record.record, record.entry?.snapshot_id)}
                >
                  {record.statusLabel} · {record.headline} ·{" "}
                  <CommitLink repository={record.entry?.repository} commit={record.entry?.commit} /> ·{" "}
                  {relativeTime(record.entry?.timestamp)}
                </DockRow>
              ))}
            </ul>
          )}
        </TabsContent>
      </ScrollArea>
    </Tabs>
  );
}

/**
 * One dock line. The whole row opens the record for pointer users; the record
 * name is the real button so the keyboard reaches it, and commit links keep
 * their own target — an anchor inside a button is invalid.
 */
function DockRow({
  lead,
  record,
  onOpen,
  children,
}: {
  lead: ReactNode;
  record: string;
  onOpen: () => void;
  children: ReactNode;
}): JSX.Element {
  return (
    <li className="flex min-h-8 cursor-pointer items-baseline gap-3 px-3 hover:bg-interactive" onClick={onOpen}>
      {lead}
      <Button
        variant="link"
        size="content"
        className="w-24 shrink-0 justify-start truncate text-label text-foreground"
        onClick={(e) => {
          e.stopPropagation();
          onOpen();
        }}
      >
        {record}
      </Button>
      <span className="min-w-0 flex-1 truncate font-mono text-label text-muted-foreground">{children}</span>
    </li>
  );
}
