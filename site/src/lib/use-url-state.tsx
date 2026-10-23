import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  EMPTY_URL_STATE,
  formatHash,
  isNavigation,
  mergeUrlState,
  parseHash,
  type UrlState,
} from "@/lib/url-state";

export type UrlPatch = Partial<UrlState> | ((current: UrlState) => Partial<UrlState>);

type UrlStateValue = [UrlState, (patch: UrlPatch) => void];

const UrlStateContext = createContext<UrlStateValue | null>(null);

/**
 * The one owner of the address-bar state.
 *
 * `history.pushState` fires neither `popstate` nor `hashchange`, so a hook
 * holding its own copy per component never hears what another component
 * wrote: a dock row would change the address and leave the open tab where it
 * was. Every reader shares this provider's state instead; the browser events
 * only bring in what the app did not write itself (Back, Forward, a
 * hand-edited address).
 */
export function UrlStateProvider({ children }: { children: ReactNode }) {
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
      if (hash === window.location.hash) return next;
      const url = `${window.location.pathname}${window.location.search}${hash}`;
      if (isNavigation(current, resolved)) window.history.pushState(null, "", url);
      else window.history.replaceState(null, "", url);
      return next;
    });
  }, []);

  const value = useMemo<UrlStateValue>(() => [state, update], [state, update]);
  return <UrlStateContext.Provider value={value}>{children}</UrlStateContext.Provider>;
}

export function useUrlState(): UrlStateValue {
  const value = useContext(UrlStateContext);
  if (!value) throw new Error("useUrlState must be used inside <UrlStateProvider>");
  return value;
}
