import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "./api";
import Alerts from "./Alerts";
import type { AlertPage } from "./api";
const page: AlertPage = { is_demo: false, unread_total: 1,
  items: [{ id: "change-1", is_manual_demo: true, is_read: false, entity_kind: "pokemon", entity_name: "bulbasaur", detected_at: "2026-10-20T12:00:00Z", changes: { "stats.attack": { before: 49, after: 60 } }, affected: [{ id: 1, name: "bulbasaur", types: ["grass", "poison"], reasons: ["catalog"], teams: [{ id: "team-1", name: "My lineup", positions: [0, 2] }] }] }],
  total: 1, limit: 10, offset: 0, window_days: 7, since: "2026-10-13T12:00:00Z", as_of: "2026-10-20T12:00:00Z", latest_scan: null };
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(100, 20, 42, 42));
  vi.spyOn(api, "markAlertsRead").mockResolvedValue(undefined);
});
afterEach(() => vi.restoreAllMocks());
it("keeps the tray closed and counts unread alerts until opened", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue(page);
  render(<Alerts membershipKey="one" />);
  const icon = await screen.findByRole("button", { name: "Alerts, 1 unread" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(api.markAlertsRead).not.toHaveBeenCalled();
  fireEvent.click(icon);
  expect(await screen.findByLabelText("Attack: 49 → 60")).toBeVisible();
  expect(screen.getByText("My lineup · slots 1, 3")).toBeVisible();
  await waitFor(() => expect(screen.getByRole("button", { name: "Alerts" })).toBeVisible());
  expect(api.markAlertsRead).toHaveBeenCalledWith(["change-1"]);
  fireEvent.click(screen.getByRole("button", { name: "Close alerts" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("does not hide unread badges if marking read fails", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue(page);
  vi.mocked(api.markAlertsRead).mockRejectedValue(new Error("network"));
  render(<Alerts membershipKey="one" />);
  fireEvent.click(await screen.findByRole("button", { name: "Alerts, 1 unread" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not mark alerts");
  expect(screen.getByRole("button", { name: "Alerts, 1 unread" })).toBeVisible();
});
it("retries failed loads and shows the empty state", async () => {
  const load = vi.spyOn(api, "getAlerts").mockRejectedValueOnce(new Error("Server unavailable")).mockResolvedValue({ ...page, total: 0, unread_total: 0, items: [] });
  render(<Alerts membershipKey="empty" />);
  fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
  expect(await screen.findByText("No recent changes affecting your saved teams.")).toBeVisible();
  expect(load.mock.calls.length).toBeGreaterThan(1);
});
it("paginates and resets to the latest page when saved membership changes", async () => {
  const load = vi.spyOn(api, "getAlerts").mockResolvedValue({ ...page, total: 11, unread_total: 0, items: [{ ...page.items[0], is_read: true }] });
  const view = render(<Alerts membershipKey="first" />);
  fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
  await screen.findByText("Bulbasaur Changed");
  fireEvent.click(screen.getByRole("button", { name: "Older alerts" }));
  await waitFor(() => expect(load).toHaveBeenLastCalledWith(10, expect.any(AbortSignal)));
  view.rerender(<Alerts membershipKey="second" />);
  await waitFor(() => expect(load).toHaveBeenLastCalledWith(0, expect.any(AbortSignal)));
});

it("uses title-case change cards, shared type badges and explicit matchup context", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue({ ...page, items: [{ ...page.items[0], entity_kind: "type", entity_name: "fire",
    changes: { "damage_to.grass": { before: 2, after: 1 } },
    affected: [{ ...page.items[0].affected[0], reasons: ["defending_type"] }] }] });
  render(<Alerts membershipKey="typed" />);
  fireEvent.click(await screen.findByRole("button", { name: "Alerts, 1 unread" }));
  expect(await screen.findByRole("heading", { name: "Fire Type Matchups Changed" })).toBeVisible();
  expect(screen.getByLabelText("Fire attacks against Grass: 2× → 1×")).toBeVisible();
  const affected = screen.getByRole("list", { name: "Affected Pokémon" });
  expect(affected.querySelector('.type-grass')).toHaveTextContent('grass');
  expect(affected.querySelector('.type-poison')).toHaveTextContent('poison');
  expect(screen.getByText("Defensive matchup changed")).toBeVisible();
});

it("groups dates and expands timestamped field history", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue({ ...page, items: [{ ...page.items[0], history: {
    "stats.attack": [
      { id: "second", detected_at: "2026-10-20T12:00:00Z", before: 60, after: 70 },
      { id: "first", detected_at: "2026-10-19T12:00:00Z", before: 49, after: 60 },
    ],
  } }] });
  render(<Alerts membershipKey="history" />);
  fireEvent.click(await screen.findByRole("button", { name: "Alerts, 1 unread" }));
  const summary = await screen.findByText("View history · Attack (2)");
  expect(summary.closest("details")).not.toHaveAttribute("open");
  fireEvent.click(summary);
  expect(screen.getByRole("list", { name: "Attack history" }).querySelectorAll("time")).toHaveLength(2);
  expect(screen.getByText("Detected changes · last 7 days · newest first")).toBeVisible();
  expect(document.querySelector(".alert-date")).toBeInTheDocument();
});

it("dismisses the popover with Escape, the bell, and an outside click", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue(page);
  render(<Alerts membershipKey="dismiss" />);
  const bell = await screen.findByRole("button", { name: "Alerts, 1 unread" });
  fireEvent.click(bell);
  expect(await screen.findByRole("dialog")).toHaveFocus();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(bell).toHaveFocus();
  fireEvent.click(bell);
  fireEvent.click(bell);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(bell);
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
