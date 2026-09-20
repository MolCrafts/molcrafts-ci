import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { IndexEntry, Snapshot } from "@/lib/snapshot-data";

export interface SnapshotSelection {
  /** The on-disk record this snapshot belongs to. */
  record: string;
  entry: IndexEntry;
  /** Body, when the surface that selected it had already read one. */
  snapshot: Snapshot | null;
}

interface SelectionStore {
  selection: SnapshotSelection | null;
  select: (next: SnapshotSelection | null) => void;
}

const SelectionContext = createContext<SelectionStore>({
  selection: null,
  select: () => {},
});

/**
 * What the inspector is looking at.
 *
 * A work surface knows which snapshot it is showing; the inspector is a
 * sibling region, not its child. This is the channel between them — the
 * alternative is every surface growing its own provenance block, which is the
 * duplication the inspector exists to end.
 */
export function SelectionProvider({
  resetKey,
  children,
}: {
  /** Clears the selection when it changes — the selected project, normally. */
  resetKey: string | null;
  children: ReactNode;
}) {
  const [selection, select] = useState<SnapshotSelection | null>(null);

  useEffect(() => {
    select(null);
  }, [resetKey]);

  const value = useMemo(() => ({ selection, select }), [selection]);

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export const useSelection = (): SnapshotSelection | null =>
  useContext(SelectionContext).selection;

export const useSelect = (): ((next: SnapshotSelection | null) => void) =>
  useContext(SelectionContext).select;
