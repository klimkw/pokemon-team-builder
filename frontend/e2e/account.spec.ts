import { randomUUID } from "node:crypto";
import { expect, request, test } from "@playwright/test";

test("register, log in, restore session, and revoke it on logout", async ({ page, browser, baseURL }, testInfo) => {
  const username = `e2e_${randomUUID().replaceAll("-", "").slice(0, 16)}`;
  const password = "Disposable-e2e-password-2026";

  await page.goto("/");
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  await page.getByRole("group", { name: "Account options" })
    .getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.locator("form").getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Account created.");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");

  // A rejected password must not create a signed-in browser session.
  await page.getByLabel("Password", { exact: true }).fill("Incorrect-e2e-password");
  await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Username or password is incorrect.");
  expect((await page.request.get("/api/auth/me")).status()).toBe(401);

  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: `You’re in, ${username}.`, exact: true })).toBeVisible();
  const cookie = (await page.context().cookies()).find(value => value.name === "pokemon_session");
  expect(cookie).toBeDefined();
  expect(cookie!.httpOnly).toBe(true);
  expect(cookie!.sameSite).toBe("Lax");

  await page.reload();
  await expect(page.getByRole("heading", { name: `You’re in, ${username}.`, exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("account-signed-in.png"), fullPage: true });

  const otherBrowser = await browser.newContext({ baseURL });
  try {
    expect((await otherBrowser.request.get("/api/auth/me")).status()).toBe(401);
  } finally {
    await otherBrowser.close();
  }

  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "You’re signed out." })).toBeVisible();
  expect((await page.request.get("/api/auth/me")).status()).toBe(401);
  expect((await page.context().cookies()).find(value => value.name === "pokemon_session")).toBeUndefined();

  // Replaying the old cookie verifies server-side revocation, not just UI state.
  const replay = await request.newContext({ baseURL, extraHTTPHeaders: { Cookie: `pokemon_session=${cookie!.value}` } });
  try {
    expect((await replay.get("/api/auth/me")).status()).toBe(401);
  } finally {
    await replay.dispose();
  }

  await page.reload();
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.locator("form").getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: `You’re in, ${username}.`, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "You’re signed out." })).toBeVisible();
});
