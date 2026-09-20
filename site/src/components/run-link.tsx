import type { JSX } from "react";

import { cn } from "@/lib/utils";

export interface RunLinkProps {
  /** `owner/name`, as the manifest records it. */
  repository: string | undefined;
  /** The workflow run id the producer published under. */
  run: number | undefined;
  className?: string;
  children?: React.ReactNode;
}

/**
 * The CI run that produced a snapshot, as a link to it.
 *
 * Every index entry already carries `repository` and `workflow_run`, which is
 * exactly `https://github.com/{repository}/actions/runs/{run}` — and until now
 * that pair was rendered as an eleven-digit number nobody could click. This is
 * where detail this site deliberately does not show (per-line coverage, full
 * logs, the job graph) is meant to be read.
 */
export function RunLink({ repository, run, className, children }: RunLinkProps): JSX.Element {
  const label = children ?? (run != null ? `#${run}` : "—");

  if (!repository || run == null) {
    return <span className={cn("font-mono", className)}>{label}</span>;
  }

  return (
    <a
      href={`https://github.com/${repository}/actions/runs/${run}`}
      target="_blank"
      rel="noreferrer"
      title={`${repository} run ${run}`}
      className={cn(
        "rounded-hairline underline-offset-4 outline-none",
        "hover:underline focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </a>
  );
}
