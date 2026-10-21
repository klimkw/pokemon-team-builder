import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import Profile from "./Profile";
import * as api from "./api";

afterEach(() => vi.restoreAllMocks());

function renderProfile(canEndSession = () => true) {
  const onUpdated = vi.fn();
  const onPasswordChanged = vi.fn().mockResolvedValue(undefined);
  render(<Profile user={{ id: "ash-id", username: "ash" }} teams={[]} busy={false}
    onBack={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn().mockResolvedValue(undefined)}
    onUpdated={onUpdated} onPasswordChanged={onPasswordChanged} canEndSession={canEndSession} />);
  return { onUpdated, onPasswordChanged };
}

it("retains profile inputs after rejection and clears credentials only after a successful retry", async () => {
  const update = vi.spyOn(api, "updateProfile")
    .mockRejectedValueOnce(new Error("Current password is incorrect"))
    .mockResolvedValueOnce({ user: { id: "ash-id", username: "ash_new" }, session_revoked: false });
  const { onUpdated, onPasswordChanged } = renderProfile();
  const user = userEvent.setup();
  await user.clear(screen.getByLabelText("Username"));
  await user.type(screen.getByLabelText("Username"), "ash_new");
  await user.type(screen.getByLabelText("Current password"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Save account" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Current password is incorrect");
  expect(screen.getByLabelText("Username")).toHaveValue("ash_new");
  expect(onUpdated).not.toHaveBeenCalled();
  await user.clear(screen.getByLabelText("Current password"));
  await user.type(screen.getByLabelText("Current password"), "correct-password");
  await user.click(screen.getByRole("button", { name: "Save account" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Account updated.");
  expect(update).toHaveBeenLastCalledWith({ username: "ash_new", current_password: "correct-password" });
  expect(screen.getByLabelText("Current password")).toHaveValue("");
  expect(onUpdated).toHaveBeenCalledWith({ id: "ash-id", username: "ash_new" });
  expect(onPasswordChanged).not.toHaveBeenCalled();
});

it("does not change a password when the user declines ending the session", async () => {
  const update = vi.spyOn(api, "updateProfile");
  const { onPasswordChanged } = renderProfile(() => false);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("New password"), "new-password");
  await user.type(screen.getByLabelText("Current password"), "current-password");
  await user.click(screen.getByRole("button", { name: "Save account" }));
  expect(update).not.toHaveBeenCalled();
  expect(onPasswordChanged).not.toHaveBeenCalled();
  expect(screen.getByLabelText("New password")).toHaveValue("new-password");
});

it("handles password-change revocation without reporting an ordinary account update", async () => {
  vi.spyOn(api, "updateProfile").mockResolvedValue({ user: { id: "ash-id", username: "ash" }, session_revoked: true });
  const { onPasswordChanged } = renderProfile();
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("New password"), "new-password");
  await user.type(screen.getByLabelText("Current password"), "current-password");
  await user.click(screen.getByRole("button", { name: "Save account" }));
  await waitFor(() => expect(onPasswordChanged).toHaveBeenCalledOnce());
  expect(screen.getByLabelText("New password")).toHaveValue("");
  expect(screen.getByLabelText("Current password")).toHaveValue("");
  expect(screen.queryByText("Account updated.")).not.toBeInTheDocument();
});
