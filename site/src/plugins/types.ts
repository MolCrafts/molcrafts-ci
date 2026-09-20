import type { ComponentType } from "react";

export interface ProjectContext {
  id: string;
  /** Snapshot records present in the published index for this project. */
  records: string[];
}

export interface RecordTabPanelProps {
  project: ProjectContext;
  /**
   * Open another registered tab.
   *
   * The overview's job ends at "what do I open next", so it needs to hand the
   * reader to the detail tab rather than re-hosting that tab's inventory.
   */
  openTab?: (tabId: string) => void;
}

export interface RecordTabPlugin {
  id: string;
  label: string;
  order?: number;
  available: (ctx: ProjectContext) => boolean;
  Component: ComponentType<RecordTabPanelProps>;
}
