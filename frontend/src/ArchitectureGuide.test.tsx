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
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("architecture walkthrough");
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
