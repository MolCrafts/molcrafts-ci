import { cn } from "@/lib/utils";
import type { ProjectContext } from "@/plugins/types";

/**
 * The navigator: find and select a project.
 *
 * Flat, because the tabs already are the record navigation — a tree that
 * expands to the same six names the tab strip shows is a second copy of one
 * control. It carries no counts or status either: those belong to the surface
 * the selection opens.
 */
export function ProjectList({
  projects,
  selectedId,
  onSelect,
}: {
  projects: ProjectContext[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="flex flex-col gap-1">
      {projects.map((project) => {
        const active = project.id === selectedId;
        return (
          <li key={project.id}>
            <button
              type="button"
              aria-current={active ? "page" : undefined}
              className={cn(
                "min-h-11 w-full truncate rounded-control px-3 py-2 text-left text-body-lg transition-colors",
                active
                  ? "bg-primary-muted font-semibold text-primary-muted-foreground"
                  : "text-foreground hover:bg-interactive",
              )}
              onClick={() => onSelect(project.id)}
            >
              {project.id}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
