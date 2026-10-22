import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ArchitectureGuide from "./ArchitectureGuide";

vi.mock("../../docs/architecture.md?raw", () => ({ default: [
  "# Reference rendering",
  "## Windows line endings",
  "![System architecture](../frontend/public/architecture.svg)",
  "See [counter model guide](counter-model.md).",
  "Read [source](https://github.com/example/repo/blob/abc/file.py#L1-L3) and `inline_code`.",
  "[unsafe](javascript:alert) [data](data:text/html,test) <script>alert(1)</script>",
  "```typescript\nconst example = '[literal](https://example.com)';\n```",
  "| Reference | Purpose |\n| --- | --- |\n| [table source](https://example.com/source) | Review |",
  "1. Follow [step source](https://example.com/step).",
].join("\r\n\r\n") }));

it("renders HTTPS references in prose, tables and steps without interpreting code or unsafe markup", () => {
  const { container } = render(<ArchitectureGuide />);
  expect(screen.getByRole("heading", { name: "Windows line endings" })).toBeVisible();
  expect(screen.getByRole("img", { name: "System architecture" })).toHaveAttribute("src", "/architecture.svg");
  for (const name of ["source", "table source", "step source"]) {
    expect(screen.getByRole("link", { name })).toHaveAttribute("target", "_blank");
  }
  expect(screen.getByRole("link", { name: "counter model guide" })).toHaveAttribute("href", "/counter-method");
  expect(screen.getByText("inline_code").tagName).toBe("CODE");
  expect(screen.queryByRole("link", { name: "unsafe" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "data" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "literal" })).not.toBeInTheDocument();
  expect(container.querySelector("script")).toBeNull();
  expect(screen.getByText(/const example/).tagName).toBe("CODE");
});
