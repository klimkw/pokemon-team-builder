import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "./api";
import Alerts from "./Alerts";
import type { AlertPage } from "./api";

const page: AlertPage = {
  is_demo: false,
  items: [{ is_manual_demo: true, id: "change-1", entity_kind: "pokemon", entity_name: "bulbasaur",
    detected_at: "2026-10-20T12:00:00Z", changes: { "stats.attack": { before: 49, after: 60 } },
    affected: [{ id: 1, name: "bulbasaur", reasons: ["catalog"], teams: [{ id: "team-1", name: "My lineup", positions: [0, 2] }] }] }],
  total: 1, limit: 10, offset: 0, window_days: 7, since: "2026-10-13T12:00:00Z", as_of: "2026-10-20T12:00:00Z",
  latest_scan: { status: "succeeded", started_at: "2026-10-20T11:59:00Z", finished_at: "2026-10-20T12:00:00Z" },
};
afterEach(() => vi.restoreAllMocks());

it("shows field differences, observation time and grouped saved slots", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue(page);
  render(<Alerts membershipKey="one" />);
  expect(await screen.findByText("bulbasaur changed")).toBeVisible();
  expect(screen.getByText("Attack: 49 → 60")).toBeVisible();
  expect(screen.getByText(/Demo change · applied manually/)).toBeVisible();
  expect(screen.getByText("My lineup · slots 1, 3")).toBeVisible();
  expect(screen.getByText(/last 7 days/)).toBeVisible();
  expect(screen.getByText(/Unsaved drafts are not included/)).toBeVisible();
});

it("explains type directions and incomplete scanner freshness", async () => {
  vi.spyOn(api, "getAlerts").mockResolvedValue({ ...page,
    is_demo: true,
    latest_scan: { ...page.latest_scan!, status: "partial" },
    items: [{ ...page.items[0], entity_kind: "type", entity_name: "fire",
      changes: { "damage_to.grass": { before: 2, after: 1 } },
      affected: [{ ...page.items[0].affected[0], reasons: ["defending_type"] }] }],
  });
  render(<Alerts membershipKey="one" />);
  expect(await screen.findByText("fire type matchups changed")).toBeVisible();
  expect(screen.getByText("fire attacks against grass: 2× → 1×")).toBeVisible();
  expect(screen.getByText(/its defensive matchup changed/)).toBeVisible();
  expect(screen.getByText(/Some source data may not have been checked/)).toBeVisible();
  expect(screen.getByText(/these changes are fictional/)).toBeVisible();
});

it("shows empty and never-scanned states and retries failed loads", async () => {
  const load = vi.spyOn(api, "getAlerts").mockRejectedValueOnce(new Error("Server unavailable"))
    .mockResolvedValue({ ...page, total: 0, items: [], window_days: 14, latest_scan: null });
  render(<Alerts membershipKey="empty" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Server unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Refresh alerts" }));
  expect(await screen.findByText("No recent changes affecting your saved teams.")).toBeVisible();
  expect(screen.getByText(/last 14 days/)).toBeVisible();
  expect(screen.getByText(/No scan has been recorded/)).toBeVisible();
  expect(load).toHaveBeenCalledTimes(2);
});

it("paginates and refreshes membership without allowing stale requests to replace results", async () => {
  const load = vi.spyOn(api, "getAlerts").mockResolvedValue({ ...page, total: 11 });
  const view = render(<Alerts membershipKey="first" />);
  await screen.findByText("bulbasaur changed");
  fireEvent.click(screen.getByRole("button", { name: "Older alerts" }));
  await waitFor(() => expect(load).toHaveBeenLastCalledWith(10, expect.any(AbortSignal)));
  await screen.findByText("bulbasaur changed");
  expect(screen.getByRole("button", { name: "Older alerts" })).toBeDisabled();
  view.rerender(<Alerts membershipKey="second" />);
  await waitFor(() => expect(load).toHaveBeenLastCalledWith(0, expect.any(AbortSignal)));
  view.unmount();
  expect(load.mock.calls.at(-1)![1]!.aborted).toBe(true);
});
