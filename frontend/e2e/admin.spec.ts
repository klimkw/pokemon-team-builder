import { expect, test } from "@playwright/test";

test("admin docs queue scanner changes, repeat without duplicates and reset in the same app", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("review_admin");
  await page.getByLabel("Password", { exact: true }).fill("Disposable-admin-password-2026");
  await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "You’re in, review_admin." })).toBeVisible();
  expect((await page.request.get("/docs")).ok()).toBeTruthy();
  const schema = await (await page.request.get("/openapi.json")).json();
  expect(schema.paths["/api/admin/demo/changes"].post).toBeTruthy();
  expect(schema.paths["/api/admin/refresh"].post).toBeTruthy();
  const saved = await page.request.post("/api/teams", { data: { name: "Admin review", pokemon_ids: [1, 1] } });
  expect(saved.ok()).toBeTruthy();
  const team = await saved.json();
  await page.reload();
  const patch = { pokemon: [{ pokemon_id: 1, stats: { attack: 60 } }], type_matchups: [{ attacking_type: "fire", defending_type: "grass", multiplier: 1 }] };
  async function run(path: string, data?: unknown) {
    const queued = await page.request.post(`/api/admin/${path}`, { data });
    expect(queued.status()).toBe(202);
    const job = await queued.json();
    let result: { status: string; result: any; error: string | null };
    await expect.poll(async () => {
      result = await (await page.request.get(`/api/admin/jobs/${job.id}`)).json();
      return result.status;
    }, { timeout: 25_000 }).toMatch(/^(succeeded|partial|failed)$/);
    expect(result!.status, result!.error ?? "job completes").toBe("succeeded");
    return result!.result;
  }
  const first = await run("demo/changes", patch);
  expect(first.pokemon.updated).toBe(1);
  await page.getByRole("button", { name: "Refresh alerts" }).click();
  await expect(page.getByRole("heading", { name: "Recent changes (2)" })).toBeVisible();
  await expect(page.getByText("Attack: 49 → 60")).toBeVisible();
  await expect(page.getByText(/Demo change · applied manually/)).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("admin-alerts.png"), fullPage: true });
  expect((await run("demo/changes", patch)).pokemon.updated).toBe(0);
  expect((await (await page.request.get("/api/alerts")).json()).total).toBe(2);
  expect((await run("demo/reset")).removed_history).toBe(2);
  await page.getByRole("button", { name: "Refresh alerts" }).click();
  await expect(page.getByText("No recent changes affecting your saved teams.")).toBeVisible();
  expect((await (await page.request.get("/api/pokemon/1")).json()).stats.attack).toBe(49);
  expect((await page.request.delete(`/api/teams/${team.id}`)).status()).toBe(204);
});
