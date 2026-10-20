import { expect, test } from "@playwright/test";

test("deterministic demo displays real scanner changes and scopes alerts to saved membership", async ({ page }, testInfo) => {
  test.skip(process.env.E2E_DEMO !== "true", "Runs only against the isolated demo stack after the change/repeat steps");
  await page.goto("/");
  await page.getByLabel("Username").fill("demo_trainer");
  await page.getByLabel("Password", { exact: true }).fill("Demo-only-password-2026");
  await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
  const alerts = page.getByRole("region", { name: "Recent changes (2)" });
  await expect(alerts).toBeVisible();
  await expect(alerts.getByText(/these changes are fictional/)).toBeVisible();
  await expect(alerts.getByText("Attack: 49 → 60")).toBeVisible();
  await expect(alerts.getByText("fire attacks against grass: 2× → 1×")).toBeVisible();
  await expect(alerts.getByText("Demo lineup · slots 1, 2", { exact: true })).toHaveCount(2);
  await expect(alerts.getByText(/Latest scan: succeeded/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("demo-alerts-desktop.png"), fullPage: true });
  const result = await (await page.request.get("/api/alerts")).json();
  expect(result.total).toBe(2);
  // Unsaved membership edits must not remove alerts for the saved team.
  await page.getByRole("button", { name: "Remove bulbasaur from slot 1" }).click();
  await page.getByRole("button", { name: "Remove bulbasaur from slot 1" }).click();
  await expect(alerts.getByText("Attack: 49 → 60")).toBeVisible();
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recent changes (1)" })).toBeVisible();
  await expect(page.getByText("bulbasaur changed", { exact: true })).toHaveCount(0);
  // The remaining charmander is still affected through its fire attacking type.
  await expect(page.getByText(/uses this attacking type/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Recent changes (1)" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("demo-alerts-mobile.png"), fullPage: true });
  // Restore the demo lineup without discarding browser state through a reload.
  const teams = await (await page.request.get("/api/teams")).json();
  expect((await page.request.put(`/api/teams/${teams[0].id}`, { data: { name: "Demo lineup", pokemon_ids: [1, 1, 4] } })).ok()).toBeTruthy();
});
