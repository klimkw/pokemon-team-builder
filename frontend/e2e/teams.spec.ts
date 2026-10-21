import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("build, save, reload, reorder, switch, and delete teams", async ({
  page,
}, testInfo) => {
  const username = `team_${randomUUID().replaceAll("-", "").slice(0, 16)}`;
  const password = "Disposable-team-password-2026";
  expect(
    (
      await page.request.post("/api/auth/register", {
        data: { username, password },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await page.request.post("/api/auth/login", {
        form: { username, password },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/");
  await expect(page.getByLabel("Team name", { exact: true })).toBeEnabled();
  await expect(
    page.getByRole("article", { name: "bulbasaur", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(
    page.getByRole("article", { name: "pikachu", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Previous", exact: true }).click();
  await page.getByLabel("Search Pokémon").fill("bulbasaur");
  await page.getByText(/^Filters/).click();
  await page.getByRole("checkbox", { name: "grass", exact: true }).check();
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.getByRole("button", { name: "Add bulbasaur to team" }).click();
  await page.getByRole("button", { name: "Add bulbasaur to team" }).click();
  await page.getByLabel("Search Pokémon").fill("charmander");
  await page.getByRole("checkbox", { name: "grass", exact: true }).uncheck();
  await page.getByRole("checkbox", { name: "fire", exact: true }).check();
  const add = page.getByRole("button", { name: "Add charmander to team" });
  for (let i = 0; i < 4; i++) await add.click();
  await expect(add).toBeDisabled();
  await page.getByLabel("Team name", { exact: true }).fill("First lineup");
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("button", { name: "Team saved.", exact: true })).toHaveClass(/team-saved/);
  await page.reload();
  await expect(page.getByLabel("Team name", { exact: true })).toHaveValue(
    "First lineup",
  );
  await expect(page.getByText("6 / 6", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Move charmander in slot 3 up" })
    .click();
  await page
    .getByRole("button", { name: "Remove bulbasaur from slot 3" })
    .click();
  await page.getByLabel("Team name", { exact: true }).fill("Edited lineup");
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("button", { name: "Team saved.", exact: true })).toHaveClass(/team-saved/);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Remove charmander from slot 2" }),
  ).toBeVisible();
  await expect(page.getByText("5 / 6", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .locator("form")
    .getByRole("button", { name: "Sign in", exact: true })
    .click();
  await expect(page.getByLabel("Team name", { exact: true })).toHaveValue(
    "Edited lineup",
  );
  await expect(
    page.getByRole("button", { name: "Remove charmander from slot 2" }),
  ).toBeVisible();
  await page.getByLabel("Saved teams").selectOption("");
  await page.getByLabel("Team name", { exact: true }).fill("Empty lineup");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByLabel("Saved teams").selectOption({ label: "Edited lineup" });
  await expect(page.getByLabel("Team name", { exact: true })).toHaveValue(
    "Empty lineup",
  );
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("button", { name: "Team saved.", exact: true })).toHaveClass(/team-saved/);
  const options = page.getByLabel("Saved teams");
  const firstId = await options
    .locator("option", { hasText: "Edited lineup" })
    .getAttribute("value");
  await options.selectOption(firstId!);
  await expect(page.getByText("5 / 6", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await page.getByRole("link", { name: "Your team · 5 / 6" }).click();
  await expect(page.getByLabel("Team name", { exact: true })).toBeInViewport();

  await expect(page.getByRole("button", { name: "New team", exact: true })).toHaveCount(0);
  const rows = page.locator(".team-member");
  const firstRow = await rows.nth(0).boundingBox();
  const nextRow = await rows.nth(1).boundingBox();
  const stats = await rows.nth(0).locator(".member-stats").boundingBox();
  expect(stats!.y + stats!.height).toBeLessThanOrEqual(firstRow!.y + firstRow!.height);
  expect(firstRow!.y + firstRow!.height).toBeLessThanOrEqual(nextRow!.y);
  await page.screenshot({
    path: testInfo.outputPath("team-builder-mobile.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 720 });
  await page.evaluate(() => window.scrollTo(0, 0));
  const pane = page.locator(".team-panel");
  const initial = await pane.boundingBox();
  await page.evaluate(() => window.scrollBy(0, 600));
  const scrolled = await pane.boundingBox();
  expect(initial!.y - scrolled!.y).toBeGreaterThan(550);
  await expect(page.getByRole("button", { name: "View optimal counter team" })).toBeInViewport();
  await expect(page.getByRole("button", { name: "Delete team", exact: true })).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY + innerHeight < document.documentElement.scrollHeight - 500)).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("team-builder-desktop.png"),
  });
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete team", exact: true }).click();
  await expect(page.getByText("Team deleted.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Team name", { exact: true })).toHaveValue(
    "Empty lineup",
  );
  const persisted = await (await page.request.get("/api/teams")).json();
  expect(persisted).toHaveLength(1);
  expect(persisted[0].members).toHaveLength(0);
});
