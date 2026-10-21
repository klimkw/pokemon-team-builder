import { expect, test as base, type APIRequestContext } from "@playwright/test";

async function runJob(request: APIRequestContext, path: string, data?: unknown) {
  const queued = await request.post(`/api/admin/${path}`, { data });
  expect(queued.status()).toBe(202);
  const job = await queued.json();
  let result: { status: string; result: { pokemon?: { updated: number }; removed_history?: number }; error: string | null };
  await expect.poll(async () => {
    result = await (await request.get(`/api/admin/jobs/${job.id}`)).json();
    return result.status;
  }, { timeout: 25_000 }).toMatch(/^(succeeded|partial|failed)$/);
  expect(result!.status, result!.error ?? "job completes").toBe("succeeded");
  return result!.result;
}

const test = base.extend<{ adminTeam: { id: string } }>({
  adminTeam: [async ({ page }, use) => {
    await page.goto("/");
    await page.getByLabel("Username").fill("review_admin");
    await page.getByLabel("Password", { exact: true }).fill("Disposable-admin-password-2026");
    await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("heading", { name: "You’re in, review_admin." })).toBeVisible();
    const saved = await page.request.post("/api/teams", { data: { name: "Admin review", pokemon_ids: [1, 1] } });
    expect(saved.ok()).toBeTruthy();
    const team = await saved.json();
    try {
      await use(team);
    } finally {
      await runJob(page.request, "demo/reset");
      expect((await page.request.delete(`/api/teams/${team.id}`)).status()).toBe(204);
    }
  }, { timeout: 30_000 }],
});

test("queued scanner changes produce readable alerts and reset without losing teams", async ({ page, adminTeam }, testInfo) => {
  await page.reload();
  const patch = { pokemon: [{ pokemon_id: 1, stats: { attack: 60 } }], type_matchups: [{ attacking_type: "fire", defending_type: "grass", multiplier: 1 }] };
  const first = await runJob(page.request, "demo/changes", patch);
  expect(first.pokemon?.updated).toBe(1);
  await page.reload();
  await expect(page.getByRole("button", { name: "Alerts, 2 unread", exact: true })).toBeVisible();
  await expect(page.locator(".unread-badge")).toHaveText("2");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: /^Alerts/ }).click();
  await page.getByRole("button", { name: "Refresh alerts" }).click();
  await expect(page.getByRole("heading", { name: "Recent changes (2)" })).toBeVisible();
  await expect(page.getByLabel("Attack: 49 → 60", { exact: true })).toBeVisible();
  await expect(page.getByText(/Demo change · applied manually/)).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Bulbasaur Changed", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fire Type Matchups Changed", exact: true })).toBeVisible();
  const affected = page.locator('.affected-pokemon').first();
  await expect(affected.locator('.type-grass')).toBeVisible();
  await expect(page.getByText('Defensive matchup changed', { exact: true })).toBeVisible();
  const nextPatch = { pokemon: [{ pokemon_id: 1, stats: { attack: 70 } }] };
  expect((await runJob(page.request, "demo/changes", nextPatch)).pokemon?.updated).toBe(1);
  await page.getByRole("button", { name: "Refresh alerts" }).click();
  await expect(page.getByRole("heading", { name: "Recent changes (3)" })).toBeVisible();
  await page.getByText("View history · Attack (2)").first().click();
  await expect(page.getByRole("list", { name: "Attack history" }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("admin-alerts.png") });
  await expect(page.locator(".unread-badge")).toHaveCount(0);
  await page.getByRole("button", { name: "Close alerts" }).click();
  await page.reload();
  await expect(page.getByRole("button", { name: "Alerts", exact: true })).toBeVisible();
  expect((await runJob(page.request, "demo/changes", nextPatch)).pokemon?.updated).toBe(0);
  expect((await (await page.request.get("/api/alerts")).json()).total).toBe(3);
  expect((await runJob(page.request, "demo/reset")).removed_history).toBe(3);
  await page.getByRole("button", { name: /^Alerts/ }).click();
  await page.getByRole("button", { name: "Refresh alerts" }).click();
  await expect(page.getByText("No recent changes affecting your saved teams.")).toBeVisible();
  expect((await (await page.request.get("/api/pokemon/1")).json()).stats.attack).toBe(49);
  const preserved = await (await page.request.get(`/api/teams/${adminTeam.id}`)).json();
  expect(preserved.members.map((member: { pokemon: { id: number } }) => member.pokemon.id)).toEqual([1, 1]);
});
