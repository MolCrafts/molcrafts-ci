import { ChevronDown, ChevronUp } from "lucide-react";
import { useState, type JSX } from "react";

import { useDock } from "@/components/layout/WorkbenchShell";
import { CommitLink } from "@/components/commit-link";
import { StatusMark } from "@/components/snapshot-status";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useProjectRecords } from "@/lib/project-records";
import { useSelect } from "@/lib/selection";
import { relativeTime, type IndexEntry } from "@/lib/snapshot-data";
import { cn } from "@/lib/utils";
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
  const { collapsed, toggle } = useDock();
  const select = useSelect();
  const [tab, setTab] = useState<DockTab>("log");

  const lines: LogLine[] = (records ?? [])
    .flatMap((record) => record.entries.map((entry) => ({ record, entry })))
    .sort((a, b) => (b.entry.timestamp ?? "").localeCompare(a.entry.timestamp ?? ""));

  const problems = (records ?? []).filter((s) => s.status === "failed");
  const problemCount = problems.length + (error ? 1 : 0);

  return (
    <>
      <div className="flex h-8 shrink-0 items-stretch gap-hairline border-b border-border px-2">
        <DockTabButton active={tab === "log"} onClick={() => setTab("log")} label="Log">
          {records && (
            <span className="font-mono text-micro tabular-nums text-muted-foreground">
              {lines.length}
            </span>
          )}
        </DockTabButton>
        <DockTabButton
          active={tab === "problems"}
          onClick={() => setTab("problems")}
          label="Problems"
        >
          {problemCount > 0 && (
            <span className="rounded-hairline bg-status-failed-soft px-1 font-mono text-micro tabular-nums text-foreground">
              {problemCount}
            </span>
          )}
        </DockTabButton>
        <span className="flex-1" />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={collapsed ? "Expand panel" : "Collapse panel"}
          title={collapsed ? "Expand panel" : "Collapse panel"}
          aria-expanded={!collapsed}
          className="my-hairline text-muted-foreground"
          onClick={toggle}
        >
          {collapsed ? <ChevronUp /> : <ChevronDown />}
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {tab === "log" ? (
          records === null ? (
            <DockSkeleton />
          ) : lines.length === 0 ? (
            <EmptyState title="Nothing published yet" density="inline" className="px-3 py-2" />
          ) : (
            <ul className="py-1">
              {lines.map(({ record, entry }, i) => (
                <li
                  key={entry.snapshot_id ?? `${record.record}-${i}`}
                  className="flex h-5 cursor-pointer items-baseline gap-3 px-3 hover:bg-interactive"
                  onClick={() => select({ record: record.record, entry, snapshot: null })}
                >
                  <span className="shrink-0 font-mono text-micro tabular-nums text-muted-foreground">
                    {entry.timestamp?.slice(0, 16).replace("T", " ") ?? "—"}
                  </span>
                  <button
                    type="button"
                    className="w-24 shrink-0 truncate rounded-hairline text-left font-mono text-micro text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onClick={(e) => {
                      e.stopPropagation();
                      select({ record: record.record, entry, snapshot: null });
                    }}
                  >
                    {record.record}
                  </button>
                  <span className="min-w-0 flex-1 truncate font-mono text-micro text-muted-foreground">
                    gen {entry.generation ?? "—"} ·{" "}
                    <CommitLink repository={entry.repository} commit={entry.commit} /> ·{" "}
                    {entry.snapshot_id ?? entry.path ?? "—"}
                  </span>
                </li>
              ))}
            </ul>
          )
        ) : records === null ? (
          <DockSkeleton />
        ) : problemCount === 0 ? (
          <EmptyState title="No problems" density="inline" className="px-3 py-2" />
        ) : (
          <ul className="py-1">
            {error && (
              <li className="flex h-5 items-baseline gap-3 px-3">
                <StatusMark status="failed" className="self-center" />
                <span className="truncate font-mono text-micro text-foreground">{error}</span>
              </li>
            )}
            {problems.map((record) => (
              <li
                key={record.record}
                className="flex h-5 cursor-pointer items-baseline gap-3 px-3 hover:bg-interactive"
                onClick={() =>
                  record.entry &&
                  select({ record: record.record, entry: record.entry, snapshot: record.snapshot })
                }
              >
                <StatusMark status="failed" className="self-center" />
                <button
                  type="button"
                  className="w-24 shrink-0 truncate rounded-hairline text-left font-mono text-micro text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (record.entry)
                      select({
                        record: record.record,
                        entry: record.entry,
                        snapshot: record.snapshot,
                      });
                  }}
                >
                  {record.record}
                </button>
                  <span className="min-w-0 flex-1 truncate font-mono text-micro text-muted-foreground">
                    {record.statusLabel} · {record.headline} ·{" "}
                    <CommitLink
                      repository={record.entry?.repository}
                      commit={record.entry?.commit}
                    />{" "}
                    · {relativeTime(record.entry?.timestamp)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </ScrollArea>
    </>
  );
}

const DockTabButton = ({
  active,
  onClick,
  label,
  children,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  children?: JSX.Element | false | null;
}): JSX.Element => (
  <button
    type="button"
    aria-current={active ? "page" : undefined}
    className={cn(
      "flex items-center gap-1 border-b-2 px-3 text-label transition-colors",
      active
        ? "border-accent font-medium text-foreground"
        : "border-transparent text-muted-foreground hover:text-foreground",
    )}
    onClick={onClick}
  >
    {label}
    {children}
  </button>
);

const DockSkeleton = (): JSX.Element => (
  <div aria-hidden="true" className="flex flex-col gap-1 p-2">
    {[0, 1, 2, 3].map((i) => (
      <div key={i} className="h-3 animate-pulse rounded-hairline bg-sunken" />
    ))}
  </div>
);
