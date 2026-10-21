import { randomUUID } from "node:crypto";
import { expect, type Page } from "@playwright/test";

export async function signInFreshAccount(page: Page) {
  const username = `e2e_${randomUUID().replaceAll("-", "").slice(0, 16)}`;
  const password = "Disposable-e2e-password-2026";
  expect((await page.request.post('/api/auth/register', { data: { username, password } })).status()).toBe(201);
  expect((await page.request.post('/api/auth/login', { form: { username, password } })).status()).toBe(204);
  await page.goto('/');
  await expect(page.getByLabel('Team name', { exact: true })).toBeEnabled();
  return { username, password };
}
