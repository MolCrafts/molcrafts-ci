import { createContext, useContext, useRef, useState, type JSX, type ReactNode } from "react";
import type { ResizablePanelHandle as PanelImperativeHandle } from "@molcrafts/design";

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@molcrafts/design";
import { cn } from "@/lib/utils";

interface DockControls {
  collapsed: boolean;
  toggle: () => void;
}

const DockContext = createContext<DockControls>({ collapsed: false, toggle: () => {} });

/** Collapse state for whatever the shell put in the dock. */
export const useDock = (): DockControls => useContext(DockContext);

/**
 * The one frame every surface renders into.
 *
 * Region sizes and resize behaviour live here and nowhere else, so a new tab
 * cannot invent its own page layout. Regions are panels separated by a 1px
 * border and a background step — never floating cards, never shadows.
 *
 * Sizes persist per user: the navigator width and the dock height are
 * remembered across sessions by the resizable group's own storage.
 */
export interface WorkbenchShellProps {
  /** Band across the top: identity once, then breadcrumb and primary verbs. */
  header: ReactNode;
  /** Find and select. */
  navigator: ReactNode;
  /** The work surface. */
  children: ReactNode;
  /** Live operations — logs and problems, as tabs in one region. */
  dock: ReactNode;
}

/** Just the dock's own tab strip stays visible when it is collapsed. */
const DOCK_COLLAPSED_PX = 32;

/** A row divider out of the vertical-by-default handle. */
const HORIZONTAL_HANDLE =
  "h-px w-full after:inset-x-0 after:left-0 after:top-1/2 after:bottom-auto after:h-1 after:w-full after:translate-x-0 after:-translate-y-1/2";

/** A shell region: fills its panel, clips its own overflow, borders its edge. */
const Region = ({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}): JSX.Element => (
  <div className={cn("flex h-full min-h-0 min-w-0 flex-col overflow-hidden", className)}>
    {children}
  </div>
);

export function WorkbenchShell({
  header,
  navigator,
  children,
  dock,
}: WorkbenchShellProps): JSX.Element {
  const dockRef = useRef<PanelImperativeHandle | null>(null);
  const [dockCollapsed, setDockCollapsed] = useState(true);

  const toggle = () => {
    const panel = dockRef.current;
    if (!panel) return;
    if (panel.isCollapsed()) panel.expand();
    else panel.collapse();
  };

  return (
    <div className="flex h-dvh min-h-0 flex-col bg-background text-foreground">
      {header}

      <ResizablePanelGroup
        direction="vertical"
        autoSaveId="molci.shell"
        autoSavePanelIds={["upper", "dock"]}
        className="min-h-0 flex-1"
      >
        <ResizablePanel id="upper" minSize="200px">
          <ResizablePanelGroup
            direction="horizontal"
            autoSaveId="molci.columns"
            autoSavePanelIds={["navigator", "work"]}
            className="min-h-0"
          >
            <ResizablePanel id="navigator" defaultSize="256px" minSize="180px" maxSize="420px">
              <nav aria-label="Projects" className="h-full"><Region className="border-r border-border bg-surface">{navigator}</Region></nav>
            </ResizablePanel>
            <ResizableHandle />
            <ResizablePanel id="work" minSize="320px">
              <main aria-label="CI records" className="h-full"><Region>{children}</Region></main>
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>

        <ResizableHandle className={HORIZONTAL_HANDLE} />

        <ResizablePanel
          id="dock"
          panelRef={dockRef}
          /* Below minSize, so the dock opens closed: logs and problems are
             what you go looking for, not what greets you. A drag or a click on
             the chevron is remembered from then on. */
          defaultSize={`${DOCK_COLLAPSED_PX}px`}
          minSize="140px"
          maxSize="70%"
          collapsible
          collapsedSize={`${DOCK_COLLAPSED_PX}px`}
          onResize={(size) => setDockCollapsed(size.inPixels <= DOCK_COLLAPSED_PX + 1)}
        >
          <DockContext.Provider value={{ collapsed: dockCollapsed, toggle }}>
            <section aria-label="Operations" className="h-full"><Region className="border-t border-border bg-surface">{dock}</Region></section>
          </DockContext.Provider>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
