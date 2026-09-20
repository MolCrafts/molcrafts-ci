import type { ComponentType } from "react";

export interface ProjectContext {
  id: string;
  /** Snapshot kinds present in the published index for this project. */
  kinds: string[];
}

export interface KindTabPanelProps {
  project: ProjectContext;
  /**
   * Open another registered tab.
   *
   * The overview's job ends at "what do I open next", so it needs to hand the
   * reader to the detail tab rather than re-hosting that tab's inventory.
   */
  openTab?: (tabId: string) => void;
}

export interface KindTabPlugin {
  id: string;
  label: string;
  order?: number;
  available: (ctx: ProjectContext) => boolean;
  Component: ComponentType<KindTabPanelProps>;
}
