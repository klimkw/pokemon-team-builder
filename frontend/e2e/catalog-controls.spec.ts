import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("sort, keyboard range sliders, consistent types and selected team stats", async ({ page }, testInfo) => {
  const username = `sort_${randomUUID().replaceAll("-", "").slice(0, 15)}`;
  await page.request.post('/api/auth/register', { data: { username, password: 'Disposable-sort-password-2026' } });
  await page.request.post('/api/auth/login', { form: { username, password: 'Disposable-sort-password-2026' } });
  await page.goto('/');
  await expect(page.getByRole('article')).toHaveCount(24);
  const sorted = page.waitForResponse(response => response.url().includes('sort=hp_desc') && response.request().method() === 'GET');
  await page.getByLabel('Sort by').selectOption('hp_desc');
  expect((await (await sorted).json()).items[0].id).toBe(1);
  await page.getByRole('button', { name: 'Add bulbasaur to team' }).click();
  await page.getByRole('button', { name: 'Add bulbasaur to team' }).click();
  const card = page.getByRole('article', { name: 'bulbasaur', exact: true });
  await expect(card.getByText('In team · 2')).toBeVisible();
  await expect(page.locator('.selected-label')).toHaveCount(1);
  await expect(card).toHaveClass(/is-selected/);
  const member = page.locator('.team-member').first();
  for (const stat of ['HP', 'Attack', 'Defense', 'Sp. Atk', 'Sp. Def', 'Speed']) {
    await expect(member.getByText(stat, { exact: true })).toBeVisible();
  }
  await page.getByText(/^Filters/).click();
  const typeFilter = page.getByRole('checkbox', { name: 'grass', exact: true }).locator('..').locator('.type-badge');
  const cardBadge = card.locator('.type-grass');
  const teamBadge = member.locator('.type-grass');
  const styles = async (locator: typeof cardBadge) => locator.evaluate(element => {
    const style = getComputedStyle(element);
    return [style.backgroundColor, style.color, style.fontFamily, style.fontSize, style.fontWeight];
  });
  expect(await styles(typeFilter)).toEqual(await styles(cardBadge));
  expect(await styles(teamBadge)).toEqual(await styles(cardBadge));
  const low = page.getByRole('slider', { name: 'Attack minimum' });
  await low.focus();
  await low.press('ArrowRight');
  await expect(low).toHaveValue('1');
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(low).toHaveValue('0');
  const track = await low.boundingBox();
  await page.mouse.move(track!.x + 9, track!.y + track!.height / 2);
  await page.mouse.down();
  await page.mouse.move(track!.x + track!.width * 0.4, track!.y + track!.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => Number(await low.inputValue())).toBeGreaterThan(60);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(low).toHaveValue('0');
  await expect(card).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('catalog-comparison-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('catalog-filters-mobile.png'), fullPage: true });
});
