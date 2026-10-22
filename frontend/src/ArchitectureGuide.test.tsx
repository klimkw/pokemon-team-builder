import { render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "./api";

afterEach(() => { window.history.replaceState(null, "", "/"); vi.restoreAllMocks(); });

it("opens the architecture deep link without authentication and navigates its full outline", () => {
  window.history.replaceState(null, "", "/architecture");
  const session = vi.spyOn(api, "getCurrentUser");
  render(<App />);
  expect(session).not.toHaveBeenCalled();
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Pokémon Team Builder Architecture");
  const outline = screen.getByRole("navigation", { name: "On this page" });
  const links = within(outline).getAllByRole("link");
  expect(links).toHaveLength(15);
  for (const link of links) expect(document.getElementById(link.getAttribute("href")!.slice(1))).not.toBeNull();
  expect(screen.getByRole("img", { name: /System architecture/ })).toHaveAttribute("src", "/architecture.svg");
  expect(screen.getByRole("link", { name: "Download Markdown" })).toHaveAttribute("download", "architecture.md");
  expect(screen.getByRole("link", { name: "Download SVG" })).toHaveAttribute("href", "/architecture.svg");
  expect(screen.getByText(/ratio\(a, b\) = round_half_up/).tagName).toBe("CODE");
  expect(screen.getByText(/USER \|\|--o\{ ACCESS_TOKEN/).tagName).toBe("CODE");
  expect(screen.getAllByRole("table")).toHaveLength(5);
});

it("connects explanations to immutable source ranges and preserves them in the download", () => {
  window.history.replaceState(null, "", "/architecture");
  render(<App />);
  const ownership = screen.getByRole("link", { name: "Excerpt: owned row lookup" });
  expect(ownership).toHaveAttribute("href", "https://github.com/klimkw/pokemon-team-builder/blob/309f3c038a00fc34c1a63ef8fb67b550aa80e7c5/backend/app/api/teams.py#L17-L24");
  expect(ownership).toHaveAttribute("target", "_blank");
  expect(ownership).toHaveAttribute("rel", "noopener noreferrer");
  expect(screen.getByText(/async def owned_team/).tagName).toBe("CODE");
  expect(screen.getByRole("link", { name: "exhaustive-assignment proof test" })).toHaveAttribute("href", expect.stringContaining("backend/tests/test_counters.py#L"));
  const markdown = decodeURIComponent(screen.getByRole("link", { name: "Download Markdown" }).getAttribute("href")!.split(",").slice(1).join(","));
  expect(markdown).toContain(`[Excerpt: owned row lookup](${ownership.getAttribute("href")})`);
});
