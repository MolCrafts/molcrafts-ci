import { X } from "lucide-react";
import { useEffect, useState, type JSX, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useSelect, useSelection } from "@/lib/selection";
import { fetchSnapshot, type Snapshot } from "@/lib/snapshot-data";

interface Field {
  label: string;
  value: ReactNode;
}

const DASH = "—";

/** Sections and separators. Never a card inside a card. */
const Group = ({ title, fields }: { title: string; fields: Field[] }): JSX.Element => (
  <section className="border-b border-border px-3 py-2 last:border-b-0">
    <h3 className="mb-2 text-label font-semibold uppercase tracking-wide text-muted-foreground">
      {title}
    </h3>
    <dl className="flex flex-col gap-hairline">
      {fields.map((field) => (
        <div key={field.label} className="flex items-baseline gap-3">
          <dt className="w-24 shrink-0 text-label text-muted-foreground">{field.label}</dt>
          <dd className="min-w-0 flex-1 break-all text-right font-mono text-label tabular-nums text-foreground">
            {field.value}
          </dd>
        </div>
      ))}
    </dl>
  </section>
);

/**
 * Where the selected snapshot came from.
 *
 * Only provenance: what it *says* is already on the work surface, and the kind
 * is already the open tab. Ten fields, not seventeen — a panel that restates
 * the centre is the thing it was built to remove.
 */
export function SnapshotInspector(): JSX.Element | null {
  const selection = useSelection();
  const select = useSelect();
  const [body, setBody] = useState<{ id: string; snapshot: Snapshot | null } | null>(null);
  const [loading, setLoading] = useState(false);

  const entryId = selection ? (selection.entry.snapshot_id ?? selection.entry.path ?? "") : null;

  /*
   * A selector that already had the body hands it over; one that did not — the
   * publish log, for instance — hands over just the index entry. Without this
   * the manifest-only fields would sit at "—" forever, which reads as "empty"
   * rather than "not fetched".
   */
  useEffect(() => {
    if (!selection || selection.snapshot || entryId == null) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchSnapshot(selection.entry).then((snap) => {
      if (cancelled) return;
      setBody({ id: entryId, snapshot: snap });
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selection, entryId]);

  if (!selection) return null;

  const { entry, stream } = selection;
  const snapshot = selection.snapshot ?? (body?.id === entryId ? body.snapshot : null);
  const settled = selection.snapshot != null || (!loading && body?.id === entryId);
  const source = snapshot?.manifest?.source;
  const tracking = snapshot?.manifest?.tracking;

  return (
    <>
      <header className="flex h-toolbar-compact shrink-0 items-center gap-2 border-b border-border pl-3 pr-1">
        <span className="min-w-0 flex-1 truncate font-mono text-label text-foreground">
          {entry.snapshot_id ?? stream}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Close inspector"
          title="Close inspector"
          className="text-muted-foreground"
          onClick={() => select(null)}
        >
          <X />
        </Button>
      </header>

      {loading && (
        <p className="border-b border-border px-3 py-2 text-label text-muted-foreground">
          Reading snapshot…
        </p>
      )}
      {settled && !snapshot && (
        <p className="border-b border-border px-3 py-2 text-label text-muted-foreground">
          Body not published — showing what the index knows.
        </p>
      )}

      <ScrollArea className="min-h-0 flex-1">
        <Group
          title="Source"
          fields={[
            { label: "Repository", value: source?.repository ?? entry.repository ?? DASH },
            { label: "Ref", value: source?.ref ?? entry.ref ?? DASH },
            { label: "Commit", value: source?.commit ?? entry.commit ?? DASH },
            {
              label: "Workflow run",
              value:
                (source?.workflow_run ?? entry.workflow_run) != null
                  ? `#${source?.workflow_run ?? entry.workflow_run}`
                  : DASH,
            },
          ]}
        />
        <Group
          title="Producer"
          fields={[
            { label: "Producer", value: snapshot?.manifest?.producer ?? entry.producer ?? DASH },
            { label: "Version", value: source?.producer_version ?? DASH },
            { label: "Profile", value: snapshot?.manifest?.profile ?? entry.profile ?? DASH },
          ]}
        />
        <Group
          title="Tracking"
          fields={[
            { label: "Generation", value: tracking?.generation ?? entry.generation ?? DASH },
            { label: "Schema", value: snapshot?.manifest?.schema_version ?? DASH },
            { label: "Path", value: entry.path ?? DASH },
          ]}
        />
      </ScrollArea>
    </>
  );
}
