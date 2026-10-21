import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("preview counters for unsaved edits, explain them, and explicitly save a separate team", async ({
  page,
}, testInfo) => {
  const username = `counter_${randomUUID().replaceAll("-", "").slice(0, 15)}`;
  const password = "Disposable-counter-password-2026";
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
  const viewCounter = page.getByRole("button", {
    name: "View optimal counter team",
  });
  await expect(viewCounter).toBeDisabled();
  await page.getByRole("button", { name: "Add bulbasaur to team" }).click();
  await page.getByLabel("Team name", { exact: true }).fill("My original");
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  await expect(page.getByRole("button", { name: "Team saved.", exact: true })).toBeVisible();
  const originalId = await page.getByLabel("Saved teams").inputValue();
  // The preview must use the unsaved two-member draft, not the saved one-member team.
  await page.getByRole("button", { name: "Add charmander to team" }).click();
  await viewCounter.click();
  const dialog = page.getByRole("dialog", { name: "Optimal counter team" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/\/ 2 safe matchups/)).toBeVisible();
  await expect(dialog.locator(".counter-matchup")).toHaveCount(2);
  await expect(
    dialog.getByText("OPPOSING SLOT 1", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByText("OPPOSING SLOT 2", { exact: true }),
  ).toBeVisible();
  expect(await (await page.request.get("/api/teams")).json()).toHaveLength(1);
  await expect(dialog.locator(".paired-cards .pokemon-card")).toHaveCount(4);
  await dialog.getByRole("button", { name: "Go to simulation ↓" }).click();
  await expect(dialog.getByRole("heading", { name: "Matchup simulation" })).toBeInViewport();
  await dialog.getByRole("button", { name: "Run matchup simulation" }).click();
  await expect(dialog.getByRole("progressbar")).toHaveCount(4);
  await dialog.getByRole("button", { name: "Show result" }).click();
  await expect(dialog.getByRole("status")).toContainText("Counter wins");
  await page.screenshot({ path: testInfo.outputPath("counter-simulation-desktop.png") });
  await dialog.getByText("Damage calculation and turn log").first().click();
  await expect(dialog.getByText(/Model: paired-base-stats-v1/).first()).toBeVisible();
  await dialog.getByRole("button", { name: "Restart simulation" }).click();
  await dialog.getByRole("button", { name: "Next turn" }).click();
  const guideTab = page.waitForEvent("popup");
  await dialog.getByRole("link", { name: /Read the scoring/ }).click();
  const guide = await guideTab;
  await expect(guide.getByRole("heading", { name: "Counter teams: scoring and simulation", exact: true })).toBeVisible();
  await expect(guide.getByText(/NOT the official Pokémon damage formula/)).toBeVisible();
  await guide.screenshot({ path: testInfo.outputPath("counter-model-guide.png") });
  await guide.close();
  await dialog
    .getByText("How we choose the optimal team", { exact: true })
    .click();
  await expect(dialog.getByText(/Moves, abilities, items/)).toBeVisible();
  await dialog
    .getByText("Compare base stats and tie-break details", { exact: true })
    .first()
    .click();
  await expect(dialog.getByRole("table")).toBeVisible();
  await dialog.getByText("Compare base stats and tie-break details", { exact: true }).first().click();
  await dialog.getByText("How we choose the optimal team", { exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await dialog.locator(".battle-replay").scrollIntoViewIfNeeded();
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("counter-simulation-mobile.png") });
  await dialog.evaluate((element) => {
    element.scrollTop = 0;
  });
  expect(
    await dialog.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("counter-team-mobile.png"),
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await dialog.getByLabel("Counter team name").fill("My saved counter");
  await dialog.getByRole("button", { name: "Save as new team" }).click();
  await expect(dialog.locator(".counter-save").getByRole("status")).toContainText(
    "Saved as “My saved counter”",
  );
  await expect(
    dialog.getByRole("button", { name: "Counter team saved" }),
  ).toBeDisabled();
  await dialog.evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: testInfo.outputPath("counter-team-desktop.png"),
  });
  await dialog.getByRole("button", { name: "Back to lineup" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByLabel("Saved teams")).toHaveValue(originalId);
  await expect(
    page.getByText("Unsaved changes", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Remove charmander from slot 2" }),
  ).toBeVisible();
  const teams = await (await page.request.get("/api/teams")).json();
  expect(teams).toHaveLength(2);
  expect(
    teams.find((team: { id: string }) => team.id === originalId).members,
  ).toHaveLength(1);
  const counter = teams.find(
    (team: { name: string }) => team.name === "My saved counter",
  );
  expect(counter.members).toHaveLength(2);
  expect(
    new Set(
      counter.members.map(
        (member: { pokemon: { id: number } }) => member.pokemon.id,
      ),
    ).size,
  ).toBe(2);
  // Closing without saving also leaves the source draft intact.
  await viewCounter.click();
  await expect(dialog.getByText(/\/ 2 safe matchups/)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  expect(await (await page.request.get("/api/teams")).json()).toHaveLength(2);
  page.once("dialog", (event) => event.accept());
  await page.getByLabel("Saved teams").selectOption(counter.id);
  await page.reload();
  await expect(page.getByLabel("Team name", { exact: true })).toHaveValue(
    "My saved counter",
  );
  await expect(page.getByText("2 / 6", { exact: true })).toBeVisible();
});
