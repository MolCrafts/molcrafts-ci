/**
 * The address bar is the app's state.
 *
 * Hash-based, not pathname-based. A static host serves 404 for any path it
 * has no file for, so pathname routing needs a rewrite rule configured on the
 * host; a hash needs nothing and survives whatever `PUBLIC_BASE` is set to.
 * Cloudflare could do the rewrite with a `_redirects` file — this stays hash
 * routing because it works without asking the host for anything.
 *
 *   #/molpy/conv?profile=linux-x86_64&snapshot=coverage-linux-x86_64-c3d4e5f
 *
 * Project and tab are navigation and push a history entry; profile and the
 * selected snapshot refine the current view and replace it, so Back steps
 * between surfaces rather than between clicks.
 */

export interface UrlState {
  project: string | null;
  tab: string | null;
  profile: string | null;
  snapshot: string | null;
}

export const EMPTY_URL_STATE: UrlState = {
  project: null,
  tab: null,
  profile: null,
  snapshot: null,
};

/** Which keys count as navigation. */
const NAVIGATION: (keyof UrlState)[] = ["project", "tab"];

export function parseHash(hash: string): UrlState {
  const raw = hash.replace(/^#\/?/, "");
  if (!raw) return EMPTY_URL_STATE;

  const [pathPart = "", queryPart = ""] = raw.split("?");
  const [project, tab] = pathPart.split("/").map((s) => decodeURIComponent(s));
  const query = new URLSearchParams(queryPart);

  return {
    project: project || null,
    tab: tab || null,
    profile: query.get("profile"),
    snapshot: query.get("snapshot"),
  };
}

export function formatHash(state: UrlState): string {
  if (!state.project) return "";
  const path = [state.project, state.tab]
    .filter((part): part is string => Boolean(part))
    .map(encodeURIComponent)
    .join("/");
  const query = new URLSearchParams();
  if (state.profile) query.set("profile", state.profile);
  if (state.snapshot) query.set("snapshot", state.snapshot);
  const qs = query.toString();
  return `#/${path}${qs ? `?${qs}` : ""}`;
}

/** True when the patch changes where the reader is, not just what is refined. */
export function isNavigation(current: UrlState, patch: Partial<UrlState>): boolean {
  return NAVIGATION.some((key) => key in patch && patch[key] !== current[key]);
}

export function mergeUrlState(current: UrlState, patch: Partial<UrlState>): UrlState {
  const next = { ...current, ...patch };
  // A different project or tab invalidates what was selected inside the old
  // one; carrying a stale snapshot id forward would point at nothing.
  if (patch.project !== undefined && patch.project !== current.project) {
    next.snapshot = patch.snapshot ?? null;
  }
  if (patch.tab !== undefined && patch.tab !== current.tab) {
    next.snapshot = patch.snapshot ?? null;
  }
  return next;
}
