import { useEffect, useState } from "react";

/**
 * Tracks a media query, so a region can leave the layout instead of squeezing it.
 *
 * The shell's panels declare real minimum widths, and three of them together
 * floor the layout at ~780px while the document allows 320px. Between those
 * two numbers nothing can satisfy the constraints and the document itself
 * scrolls sideways. A region that is context rather than content can be
 * dropped at a width instead, which is what this answers.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const list = window.matchMedia(query);
    const onChange = () => setMatches(list.matches);
    onChange();
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}
