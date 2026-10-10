import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("shared UI, history charts, record deep links, native picker and theme", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/#/molcrafts-ci/overview");
  await expect(page.getByRole("heading", { name: "MolCrafts CI" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Overview", exact: true })).toHaveAttribute("aria-selected", "true");
  const charts = page.getByRole("figure", { name: "Record measurement history", exact: true });
  await expect(charts.first()).toHaveAttribute("data-chart-state", "ready");
  await expect(charts.first().locator("svg")).toBeVisible();
  expect(await page.locator("molplot-chart").count()).toBe(0);
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(charts.first()).toHaveAttribute("data-chart-state", "ready");
  await page.getByRole("tab", { name: "Coverage", exact: true }).click();
  await expect(page).toHaveURL(/#\/molcrafts-ci\/conv/);
  const picker = page.getByRole("combobox", { name: "Published generation" });
  await expect(picker).toBeVisible();
  const options = await picker.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
  expect(options.length).toBeGreaterThan(1);
  await picker.selectOption(options[1]);
  await expect(page).toHaveURL(/snapshot=/);
  await page.reload();
  await expect(picker).toHaveValue(options[1]);
  await expect(page.getByRole("button", { name: "Switch to light theme" })).toBeVisible();
  await page.setViewportSize({ width: 896, height: 720 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.map(({ id, nodes }) => ({ id, targets: nodes.map(node => node.target) }))).toEqual([]);
  expect(errors).toEqual([]);
});

test("project switching and unavailable data keep application behavior", async ({ page }) => {
  await page.goto("/#/molcrafts-ci");
  await page.getByRole("button", { name: "molrs", exact: true }).click();
  await expect(page).toHaveURL(/#\/molrs/);
  await expect(page.getByRole("tab", { name: "Overview", exact: true })).toBeVisible();
  await page.route("**/data/index-listing.json", route => route.abort());
  await page.reload();
  await expect(page.getByText("Failed to load index", { exact: true })).toBeVisible();
});
