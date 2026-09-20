import { overviewPlugin } from "../overview";
import { registerPlugin } from "../registry";
import { STREAM_KINDS } from "../stream-kinds";
import { makeStreamTab } from "../stream-tab";

/**
 * Builtin tabs. Domain packages can `registerPlugin(...)` from their own
 * modules without editing this shell — import that module from the app entry
 * (or a side-effect barrel) so registration runs at load time.
 *
 * Every stream uses the same tab: what a kind looks like is decided by its
 * payload shape in `PayloadView`, not by a hand-written panel per kind. A kind
 * earns its own Component only when its reading genuinely differs.
 */
registerPlugin(overviewPlugin);

for (const kind of STREAM_KINDS) {
  registerPlugin(makeStreamTab(kind));
}
