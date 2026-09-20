import { overviewPlugin } from "../overview";
import { registerPlugin } from "../registry";
import { RECORDS } from "../records";
import { makeRecordTab } from "../record-tab";

/**
 * Builtin tabs. Domain packages can `registerPlugin(...)` from their own
 * modules without editing this shell — import that module from the app entry
 * (or a side-effect barrel) so registration runs at load time.
 *
 * Every record uses the same tab: what a record looks like is decided by its
 * payload shape in `PayloadView`, not by a hand-written panel per record. A record
 * earns its own Component only when its reading genuinely differs.
 */
registerPlugin(overviewPlugin);

for (const record of RECORDS) {
  registerPlugin(makeRecordTab(record));
}
