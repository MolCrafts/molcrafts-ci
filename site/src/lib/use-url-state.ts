import { useCallback, useEffect, useState } from "react";

import {
  EMPTY_URL_STATE,
  formatHash,
  isNavigation,
  mergeUrlState,
  parseHash,
  type UrlState,
} from "@/lib/url-state";

/**
 * Two-way binding between the hash and React state.
 *
 * Listens for `popstate` and `hashchange` so Back, Forward and a hand-edited
 * address all land in the app rather than only reloading it.
 */
export type UrlPatch = Partial<UrlState> | ((current: UrlState) => Partial<UrlState>);

export function useUrlState(): [UrlState, (patch: UrlPatch) => void] {
  const [state, setState] = useState<UrlState>(() =>
    typeof window === "undefined" ? EMPTY_URL_STATE : parseHash(window.location.hash),
  );

  useEffect(() => {
    const sync = () => setState(parseHash(window.location.hash));
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
    };
  }, []);

  const update = useCallback((patch: UrlPatch) => {
    setState((current) => {
      // An updater form lets a caller decide against the live state — the
      // index load needs "keep the project the link named, else pick one".
      const resolved = typeof patch === "function" ? patch(current) : patch;
      const next = mergeUrlState(current, resolved);
      const hash = formatHash(next);
      if (hash === window.location.hash) return current;
      const url = `${window.location.pathname}${window.location.search}${hash}`;
      if (isNavigation(current, resolved)) window.history.pushState(null, "", url);
      else window.history.replaceState(null, "", url);
      return next;
    });
  }, []);

  return [state, update];
}
