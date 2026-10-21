import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import ModelGuide from "./ModelGuide";

it("renders repo-managed model formulas, limitations and downloadable Markdown", () => {
  render(<ModelGuide />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Counter teams");
  expect(screen.getByText(/NOT the official Pokémon damage formula/)).toBeVisible();
  expect(screen.getByText(/stats_score = attack_potential/)).toBeVisible();
  expect(screen.getByRole("link", { name: "Download Markdown" })).toHaveAttribute("download", "counter-model.md");
});
