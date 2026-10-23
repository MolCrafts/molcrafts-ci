import { defineMock, defineMockData } from "rspack-plugin-mock/helper";

import { fixtures, type IndexEntry } from "./fixtures";

const store = defineMockData("molcrafts-ci-fixtures", fixtures);

function snapshotKey(params: Record<string, string>): string {
  return `snapshots/${params.project}/${params.record}/${params.generation}/${params.file}`;
}

function toJsonl(rows: IndexEntry[]): string {
  if (rows.length === 0) return "";
  return `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`;
}

export default defineMock([
  {
    url: "/data/index-listing.json",
    method: "GET",
    body: () => ({
      indexes: store.value.indexes,
      published: store.value.published ?? {},
    }),
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
    // Like the CDN: a missing body is a 404, not a 200 with an error in it.
    response(req, res) {
      const snapshot = store.value.snapshots?.[snapshotKey(req.params)];
      res.statusCode = snapshot ? 200 : 404;
      res.setHeader("Content-Type", snapshot ? "application/json" : "text/plain");
      res.end(snapshot ? JSON.stringify(snapshot) : "Not Found");
    },
  },
]);
