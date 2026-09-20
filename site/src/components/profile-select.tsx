import { Layers } from "lucide-react";
import type { JSX } from "react";

export interface ProfileSelectProps {
  /** Every profile the selected project publishes under, sorted. */
  profiles: string[];
  value: string | null;
  onChange: (profile: string | null) => void;
}

/**
 * Which build profile the project is read at.
 *
 * A project can publish the same commit under several profiles — molrs ships
 * benchmarks for linux-x86_64 and macos-aarch64 — and a history series has to
 * stay inside one of them or it plots two machines as one trend. Without this
 * control the other profile is simply unreachable.
 *
 * Renders nothing when there is nothing to choose between.
 */
export function ProfileSelect({ profiles, value, onChange }: ProfileSelectProps): JSX.Element | null {
  if (profiles.length < 2) return null;

  return (
    <label
      className="flex items-center gap-1.5 text-label text-muted-foreground"
      title="Build profile"
    >
      <Layers className="size-icon-sm" aria-hidden="true" />
      <span className="sr-only">Build profile</span>
      <select
        className="h-control-compact rounded-control border border-border bg-surface px-2 font-mono text-label text-foreground"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        {profiles.map((profile) => (
          <option key={profile} value={profile}>
            {profile}
          </option>
        ))}
      </select>
    </label>
  );
}
