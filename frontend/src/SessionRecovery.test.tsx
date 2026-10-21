import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import SessionRecovery from "./SessionRecovery";
import * as api from "./api";

afterEach(() => vi.restoreAllMocks());

it("rejects a different account before allowing access to the retained draft", async () => {
  vi.spyOn(api, "login").mockResolvedValueOnce({ id: "different-account", username: "ash" })
    .mockResolvedValueOnce({ id: "original-account", username: "ash" });
  const logout = vi.spyOn(api, "logout").mockResolvedValue(undefined);
  const recovered = vi.fn();
  render(<SessionRecovery user={{ id: "original-account", username: "ash" }} onRecovered={recovered} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Password"), "a-valid-password");
  await user.click(screen.getByRole("button", { name: "Sign in and keep editing" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Please use the original account");
  expect(logout).toHaveBeenCalledOnce();
  expect(recovered).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Sign in and keep editing" }));
  await waitFor(() => expect(recovered).toHaveBeenCalledWith({ id: "original-account", username: "ash" }));
});
