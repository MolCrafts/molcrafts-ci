import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { scientificBenchmark } from "../fixtures/scientific-benchmark";

async function campaignData(page: Page, invalid = false) {
  const first = scientificBenchmark(), second = scientificBenchmark();
  second.campaign_id = "campaign-two";
  second.results[0]!.numerical = "fail";
  Object.assign(second.summary, { passed: 3, failed: 1, complete: false });
  second.matrix.rows[0]!.values["atv.cpu.direct"]![0] = "water-1: fail; energy mismatch; ratio ineligible";
  if (invalid) Object.assign(second, { schema: "atomiverse.scientific-benchmark/2", passed: 999, failed: 0 });
  const entries = [first, second].map((b, i) => ({
    snapshot_id: `benchmark-5-gh200-g1-${b.campaign_id}`, observation_id: b.campaign_id,
    path: `snapshots/atomiverse/benchmark/1/${b.campaign_id}.json`, record: "benchmark",
    profile: "gh200", generation: 1, repository: "MolCrafts/Atomiverse", commit: "abc123",
    producer: "atomiverse-benchmarks", timestamp: `2026-10-26T1${i}:00:00Z`,
  }));
  await page.route("**/data/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("index-listing.json")) return route.fulfill({ json: {
      indexes: ["index/atomiverse/benchmark.jsonl"], published: { atomiverse: entries[1]!.timestamp },
    } });
    if (path.endsWith("benchmark.jsonl")) return route.fulfill({ contentType: "text/plain", body: entries.map(e => JSON.stringify(e)).join("\n") });
    const i = path.includes("campaign-one.json") ? 0 : 1;
    return route.fulfill({ json: { manifest: { observation_id: entries[i]!.observation_id }, payload: [first, second][i] } });
  });
}

test("scientific matrix, hardware notes, environment and same-commit history", async ({ page }) => {
  await campaignData(page);
  await page.goto("/#/atomiverse/overview");
  await expect(page.getByText("1 numerical failed", { exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Benchmark", exact: true }).click();
  const matrix = page.getByRole("table", { name: "Scientific benchmark matrix" });
  await expect(matrix).toBeVisible();
  const headers = await matrix.getByRole("columnheader").allTextContents();
  expect(headers).toEqual(["Method / model / task", "Systems", "atv.cpu.direct", "pyscf.cpu", "Hardware / environment"]);
  await expect(matrix.getByText("water-1: fail; energy mismatch; ratio ineligible")).toBeVisible();
  await expect(page.getByText(/H1: CPU=Synthetic test CPU/)).toBeVisible();
  await page.getByText("Actual environment and protocol", { exact: true }).click();
  await expect(page.getByText(/"SLURM_JOB_ID": "test-only"/)).toBeVisible();
  const history = page.getByRole("combobox", { name: "Published generation" });
  await expect(history.locator("option")).toHaveText([/campaign-two/, /campaign-one/]);
  await history.selectOption("benchmark-5-gh200-g1-campaign-one");
  await expect(matrix.getByText("water-1: pass; 0.001 s; 1.5× vs pyscf.cpu")).toBeVisible();
  await expect(page.getByText(/Historical comparison: unbaselined/)).toBeVisible();
  await page.setViewportSize({ width: 896, height: 720 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  expect((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id)).toEqual([]);
});

test("invalid scientific payload cannot render generic passing counts", async ({ page }) => {
  await campaignData(page, true);
  await page.goto("/#/atomiverse/overview");
  await expect(page.getByText("invalid benchmark payload", { exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Benchmark", exact: true }).click();
  await expect(page.getByText("Invalid scientific benchmark", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Scientific benchmark matrix" })).toHaveCount(0);
  await expect(page.getByText("999", { exact: true })).toHaveCount(0);
});
