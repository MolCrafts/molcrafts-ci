import { createContext, useContext, useRef, useState, type JSX, type ReactNode } from "react";
import type { PanelImperativeHandle } from "react-resizable-panels";

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useMediaQuery } from "@/lib/use-media-query";
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
 * Sizes persist per user: the navigator and inspector widths and the dock
 * height are remembered across sessions by the resizable group's own storage.
 */
export interface WorkbenchShellProps {
  /** Band across the top: identity once, then breadcrumb and primary verbs. */
  header: ReactNode;
  /** Find and select. */
  navigator: ReactNode;
  /** The work surface. */
  children: ReactNode;
  /**
   * Context for the current selection, or null when nothing is selected.
   *
   * Null means the column is not rendered at all. `expand()` on a panel that
   * has never had a size does nothing — it restores "its most recent size" and
   * there is none — so mounting is what opens it, not the collapse API.
   */
  inspector: ReactNode | null;
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
  inspector,
  dock,
}: WorkbenchShellProps): JSX.Element {
  const dockRef = useRef<PanelImperativeHandle | null>(null);
  const [dockCollapsed, setDockCollapsed] = useState(true);

  /*
   * The inspector leaves the layout before the layout breaks.
   *
   * navigator 180 + work 320 + inspector 280 floors the group at ~780px while
   * the document allows 320px, so between those widths the panels cannot be
   * satisfied and the page scrolls sideways. The inspector is context for a
   * selection, not the work itself, so it is the region that yields. Below
   * ~520px the navigator would have to yield too — that needs a way to reach
   * projects without it, which is a product decision, not a layout one.
   */
  const roomForInspector = useMediaQuery("(min-width: 1024px)");

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
            /* The id set keys the persisted layout, so hiding the inspector
               does not overwrite the three-column one. */
            autoSavePanelIds={
              inspector && roomForInspector
                ? ["navigator", "work", "inspector"]
                : ["navigator", "work"]
            }
            className="min-h-0"
          >
            {/* Each panel's own flex column lives in a plain div: the panel
                primitive owns its box, so layout classes go on the content. */}
            <ResizablePanel id="navigator" defaultSize="256px" minSize="180px" maxSize="420px">
              <Region className="border-r border-border bg-surface">{navigator}</Region>
            </ResizablePanel>
            <ResizableHandle />
            <ResizablePanel id="work" minSize="320px">
              <Region>{children}</Region>
            </ResizablePanel>
            {inspector && roomForInspector && (
              <>
                <ResizableHandle />
                <ResizablePanel
                  id="inspector"
                  defaultSize="300px"
                  minSize="280px"
                  maxSize="480px"
                >
                  <Region className="border-l border-border bg-surface">{inspector}</Region>
                </ResizablePanel>
              </>
            )}
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
            <Region className="border-t border-border bg-surface">{dock}</Region>
          </DockContext.Provider>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
