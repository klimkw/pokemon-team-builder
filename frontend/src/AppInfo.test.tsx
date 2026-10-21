import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AppInfo from "./AppInfo";
import * as api from "./api";

const data: api.AppInfo = { app_version: "0.1.0", counter_model: "safe-coverage-v2-duplicates", simulation_model: "paired-base-stats-v1",
  repository_url: "https://github.com/klimkw/pokemon-team-builder", catalog_count: 1351, scan_interval_hours: 24, alert_window_days: 7,
  latest_live_refresh: null, last_successful_live_refresh: null, checked_at: "2026-10-20T12:00:00Z" };
afterEach(() => vi.restoreAllMocks());
it("loads info only on opening and displays safe metadata and links", async () => {
  const load = vi.spyOn(api, "getAppInfo").mockResolvedValue(data);
  render(<AppInfo />);
  expect(load).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "App info" }));
  expect(await screen.findByText("1,351 entries")).toBeVisible();
  expect(screen.getByText("Not scanned yet")).toBeVisible();
  expect(screen.getByRole("link", { name: "Repository ↗" })).toHaveAttribute("href", data.repository_url);
  fireEvent.click(screen.getByRole("button", { name: "Close app info" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("shows an error and supports a fresh info request", async () => {
  vi.spyOn(api, "getAppInfo").mockRejectedValueOnce(new Error("Server unavailable")).mockResolvedValue(data);
  render(<AppInfo />);
  fireEvent.click(screen.getByRole("button", { name: "App info" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Server unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Refresh info" }));
  expect(await screen.findByText("24 hours")).toBeVisible();
});
