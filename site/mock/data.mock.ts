import { defineMock, defineMockData } from "rspack-plugin-mock/helper";

import { fixtures, type IndexEntry } from "./fixtures";

const store = defineMockData("molcrafts-ci-fixtures", fixtures);

function toJsonl(rows: IndexEntry[]): string {
  if (rows.length === 0) return "";
  return `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`;
}

export default defineMock([
  {
    url: "/data/index-listing.json",
    method: "GET",
    body: () => ({ indexes: store.value.indexes }),
  },
  {
    url: "/data/index/:project/:record.jsonl",
    method: "GET",
    headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
    body: ({ params }) => {
      const key = `${params.project}/${params.record}`;
      return toJsonl(store.value.entries[key] ?? []);
    },
  },
  {
    url: "/data/snapshots/:project/:record/:generation/:file",
    method: "GET",
    body: ({ params }) => {
      const key = `snapshots/${params.project}/${params.record}/${params.generation}/${params.file}`;
      const snap = store.value.snapshots?.[key];
      if (!snap) {
        return { error: "snapshot not found", key };
      }
      return snap;
    },
  },
]);
