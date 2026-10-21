import { expect, test } from "@playwright/test";
import { signInFreshAccount } from "./helpers";

for (const width of [1280, 390]) {
  test(`revoked session preserves and saves the draft after real login at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const { password } = await signInFreshAccount(page);
    await page.getByRole('button', { name: 'Add bulbasaur to team' }).click();
    if (width === 390) await page.getByRole('button', { name: /Team · 1\/6/ }).click();
    await page.getByLabel('Team name', { exact: true }).fill('Recovered lineup');
    // Revoke the real server session without unmounting the UI or changing its draft.
    expect((await page.request.post('/api/auth/logout')).status()).toBe(204);
    expect((await page.request.get('/api/auth/me')).status()).toBe(401);
    await page.getByRole('button', { name: 'Save team', exact: true }).click();
    const recovery = page.getByRole('dialog', { name: 'Continue building' });
    await recovery.getByLabel('Password', { exact: true }).fill('wrong-password');
    await recovery.getByRole('button', { name: 'Sign in and keep editing' }).click();
    await expect(recovery.getByRole('alert')).toBeVisible();
    await recovery.getByLabel('Password', { exact: true }).fill(password);
    await recovery.getByRole('button', { name: 'Sign in and keep editing' }).click();
    await expect(recovery).toHaveCount(0);
    expect((await page.request.get('/api/auth/me')).status()).toBe(200);
    if (width === 390 && !(await page.getByRole('dialog', { name: 'Edit your team' }).isVisible())) {
      await page.getByRole('button', { name: /Team · 1\/6/ }).click();
    }
    await expect(page.getByLabel('Team name', { exact: true })).toHaveValue('Recovered lineup');
    await page.getByRole('button', { name: 'Save team', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Team saved.', exact: true })).toBeDisabled();
    const saved = await (await page.request.get('/api/teams')).json();
    expect(saved).toHaveLength(1);
    expect(saved[0].name).toBe('Recovered lineup');
    expect(saved[0].members.map((member: { pokemon: { id: number } }) => member.pokemon.id)).toEqual([1]);
    await page.reload();
    if (width === 390) await page.getByRole('button', { name: /Team · 1\/6/ }).click();
    await expect(page.getByLabel('Team name', { exact: true })).toHaveValue('Recovered lineup');
    await expect(page.getByRole('button', { name: 'Remove bulbasaur from slot 1' })).toBeVisible();
  });
}
