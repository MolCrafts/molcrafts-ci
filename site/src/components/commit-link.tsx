import type { JSX } from "react";

import { shortCommit } from "@/lib/snapshot-data";
import { cn } from "@/lib/utils";

export interface CommitLinkProps {
  /** `owner/name`, as the manifest records it. */
  repository: string | undefined;
  commit: string | undefined;
  className?: string;
}

/**
 * A commit, as a link to the commit.
 *
 * Every snapshot records the repository and the full sha, so there is no
 * reason to make a reader copy seven characters into a search box. Falls back
 * to plain text when the manifest carries no repository — the sha alone is not
 * enough to build a URL.
 */
export function CommitLink({ repository, commit, className }: CommitLinkProps): JSX.Element {
  const label = shortCommit(commit);

  if (!repository || !commit) {
    return <span className={cn("font-mono", className)}>{label}</span>;
  }

  return (
    <a
      href={`https://github.com/${repository}/commit/${commit}`}
      target="_blank"
      rel="noreferrer"
      title={`${repository}@${commit}`}
      className={cn(
        "rounded-hairline font-mono underline-offset-4 outline-none",
        "hover:underline focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </a>
  );
}
