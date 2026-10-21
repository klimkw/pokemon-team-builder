import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AppInfo from "./AppInfo";
import * as api from "./api";

const data: api.AppInfo = { app_version: "0.1.0",
  repository_url: "https://github.com/klimkw/pokemon-team-builder", catalog_source_url: "https://pokeapi.co/api/v2/pokemon/?limit=200", catalog_count: 1351, scan_interval_hours: 24, alert_window_days: 7,
  last_successful_live_refresh: null, checked_at: "2026-10-20T12:00:00Z" };
afterEach(() => vi.restoreAllMocks());
it("loads info only on opening and displays safe metadata and links", async () => {
  const load = vi.spyOn(api, "getAppInfo").mockResolvedValue(data);
  render(<AppInfo />);
  expect(load).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "App info" }));
  expect(await screen.findByText("1,351 entries")).toBeVisible();
  expect(screen.getByRole("link", { name: "PokéAPI ↗" })).toHaveAttribute("href", data.catalog_source_url);
  expect(screen.getByText("None recorded")).toBeVisible();
  expect(screen.queryByText("Latest live refresh")).not.toBeInTheDocument();
  expect(screen.queryByText("Counter model")).not.toBeInTheDocument();
  expect(screen.queryByText("Simulation model")).not.toBeInTheDocument();
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
