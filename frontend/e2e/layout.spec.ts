import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`browser-only layout and loading focus at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 844 });
    const pokemon = Array.from({ length: 48 }, (_, i) => ({ id: i + 1, name: `partner-${i + 1}`, types: ["grass"], sprite_url: null,
      stats: { hp: 45, attack: 49, defense: 49, special_attack: 65, special_defense: 65, speed: 45 } }));
    let slow = false;
    let releaseRequest: (() => void) | undefined;
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url());
      const method = route.request().method();
      let body: unknown = {};
      let status = 200;
      if (url.pathname === "/api/auth/me") body = { id: "ash", username: "ash" };
      else if (url.pathname === "/api/teams" && method === "GET") body = [{ id: "original", name: "Original", members: [] }];
      else if (url.pathname === "/api/alerts") body = { items: [], total: 0, unread_total: 0, limit: 10, offset: 0, window_days: 7 };
      else if (url.pathname === "/api/pokemon") {
        if (slow) await new Promise<void>(resolve => { releaseRequest = resolve; });
        const offset = Number(url.searchParams.get("offset") || 0);
        body = { items: pokemon.slice(offset, offset + 24), total: 48, offset, limit: 24 };
      }
      await route.fulfill({ status, json: body });
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Add partner-1 to team", exact: true }).click();
    await page.evaluate(() => window.scrollTo(0, 900));
    const editor = page.getByRole("dialog", { name: "Edit your team" });
    const pane = page.locator(".team-editor-host > .team-panel");
    if (width > 850) {
      await expect(page.locator(".team-dock")).toHaveCount(0);
      await pane.scrollIntoViewIfNeeded();
      await pane.hover();
      const scrollBefore = await page.evaluate(() => window.scrollY);
      await page.mouse.wheel(0, 300);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(scrollBefore);
      await pane.getByLabel("Team name").fill("Keep this lineup");
      await pane.getByRole("button", { name: "Save team", exact: true }).scrollIntoViewIfNeeded();
      await expect(pane.getByRole("button", { name: "Save team", exact: true })).toBeInViewport();
    } else {
      await page.getByRole("button", { name: /Team · 1\/6/ }).click();
      await editor.getByLabel("Team name").fill("Keep this lineup");
      await page.keyboard.press("Escape");
      await expect(editor).not.toBeVisible();
      await expect(page.getByRole("button", { name: /Team · 1\/6/ })).toBeFocused();
    }
    await page.screenshot({ path: testInfo.outputPath(`editor-${width}.png`) });
    slow = true;
    await page.getByLabel("Search Pokémon").fill("partner");
    await expect(page.getByText(/Updating Pokémon/)).toBeVisible();
    await expect(page.getByRole("article")).toHaveCount(24);
    await expect(page.getByLabel("Search Pokémon")).toBeFocused();
    await expect.poll(() => Boolean(releaseRequest)).toBe(true);
    slow = false;
    releaseRequest!();
    await expect(page.getByText(/Updating Pokémon/)).toHaveCount(0);
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByRole("article").first()).toHaveAttribute("aria-label", "partner-25");
    await expect(page.getByRole("region", { name: "Pokémon catalog" })).toBeFocused();
    await page.getByRole("button", { name: "Previous", exact: true }).click();
    await page.getByLabel("Search Pokémon").focus();
    await expect(page.getByRole("article").first()).toHaveAttribute("aria-label", "partner-1");
    await expect(page.getByLabel("Search Pokémon")).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`workspace-${width}.png`) });
    expect(errors).toEqual([]);
  });
}
