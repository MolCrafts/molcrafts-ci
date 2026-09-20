import type { JSX, ReactNode } from "react";

import { ScrollArea } from "@/components/ui/scroll-area";

/**
 * The one layout every tab renders into.
 *
 * Padding, gap and scroller live here so switching tabs never shifts the
 * content: whatever the surface is, its first row starts at the same place and
 * scrolls with the same chrome. A tab that lays itself out is how a tab strip
 * starts to feel jumpy.
 */
export function WorkSurface({ children }: { children: ReactNode }): JSX.Element {
  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-4 p-4">{children}</div>
    </ScrollArea>
  );
}
