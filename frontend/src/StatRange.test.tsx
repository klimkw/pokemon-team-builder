import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import StatRange from "./StatRange";
it("exposes both handles and clamps bounds without crossing", () => {
  const changed = vi.fn();
  render(<StatRange label="Attack" maximum={255} low={40} high={100} onChange={changed} />);
  expect(screen.getByRole("slider", { name: "Attack minimum" })).toHaveValue("40");
  expect(screen.getByRole("slider", { name: "Attack maximum" })).toHaveValue("100");
  expect(screen.getByText("40–100")).toBeVisible();
  fireEvent.change(screen.getByRole("slider", { name: "Attack minimum" }), { target: { value: "120" } });
  expect(changed).toHaveBeenLastCalledWith(100, 100);
  fireEvent.change(screen.getByRole("slider", { name: "Attack maximum" }), { target: { value: "20" } });
  expect(changed).toHaveBeenLastCalledWith(40, 40);
});
