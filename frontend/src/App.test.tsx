import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const user = { id: "0b980121-cfa0-4ead-8348-0d4305b08c36", username: "ash" };
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const signedOut = () => json({ detail: "Unauthorized" }, 401);

afterEach(() => vi.unstubAllGlobals());

// Keep account request sequencing independent of the signed-in workspace loads.
function stubFetch(_name: string, authFetch: typeof fetch) {
  vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("/api/alerts?")) return Promise.resolve(json({ items: [], total: 0, limit: 10, offset: 0, window_days: 7, latest_scan: null }));
    if (url === "/api/teams") return Promise.resolve(json([]));
    if (url.startsWith("/api/pokemon?"))
      return Promise.resolve(
        json({ items: [], total: 0, limit: 24, offset: 0 }),
      );
    return authFetch(input, init);
  });
}

async function fillCredentials() {
  const browser = userEvent.setup();
  await browser.type(await screen.findByLabelText("Username"), "Ash");
  await browser.type(
    screen.getByLabelText("Password", { exact: true }),
    "long-test-password",
  );
  return browser;
}

describe("account flow through the API client", () => {
  it("restores a session on page load without asking for a password", async () => {
    stubFetch("fetch", vi.fn().mockResolvedValue(json(user)));
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "You’re in, ash." }),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Password", { exact: true }),
    ).not.toBeInTheDocument();
  });

  it("submits form-encoded login, then loads the current user", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(signedOut())
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(json(user));
    stubFetch("fetch", fetchMock);
    render(<App />);
    const browser = await fillCredentials();
    await browser.click(
      within(screen.getByLabelText("Username").closest("form")!).getByRole(
        "button",
        { name: "Sign in" },
      ),
    );
    expect(
      await screen.findByRole("heading", { name: "You’re in, ash." }),
    ).toBeVisible();
    const [url, options] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/auth/login");
    expect(options.body).toBeInstanceOf(URLSearchParams);
    expect(options.body.get("username")).toBe("Ash");
    expect(options.body.get("password")).toBe("long-test-password");
    expect(options.credentials).toBe("same-origin");
  });

  it("registers with JSON and returns to sign-in without silently logging in", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(signedOut())
      .mockResolvedValueOnce(json(user, 201));
    stubFetch("fetch", fetchMock);
    render(<App />);
    const browser = userEvent.setup();
    await browser.click(
      await screen.findByRole("button", {
        name: "Create account",
      }),
    );
    await fillCredentials();
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Account created.",
    );
    expect(screen.getByLabelText("Username")).toHaveValue("Ash");
    expect(screen.getByLabelText("Password", { exact: true })).toHaveValue("");
    const [url, options] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/auth/register");
    expect(JSON.parse(options.body)).toEqual({
      username: "Ash",
      password: "long-test-password",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows a useful error for incorrect credentials and permits another attempt", async () => {
    stubFetch(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(signedOut())
        .mockResolvedValueOnce(json({ detail: "LOGIN_BAD_CREDENTIALS" }, 400)),
    );
    render(<App />);
    await fillCredentials();
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Username or password is incorrect.",
    );
    expect(screen.getByLabelText("Username")).toBeEnabled();
    expect(
      screen.queryByRole("heading", { name: /You’re in/ }),
    ).not.toBeInTheDocument();
  });

  it("keeps an outage distinct from a signed-out session and supports retry", async () => {
    stubFetch(
      "fetch",
      vi
        .fn()
        .mockRejectedValueOnce(new TypeError("network failed"))
        .mockResolvedValueOnce(signedOut()),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to reach the server.",
    );
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Retry connection/ }),
    );
    expect(await screen.findByLabelText("Username")).toBeVisible();
  });

  it("does not claim logout succeeded on server failure; an expired session can sign out", async () => {
    stubFetch(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(user))
        .mockResolvedValueOnce(json({}, 500))
        .mockResolvedValueOnce(signedOut()),
    );
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: /Sign out/ }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "server is unavailable",
    );
    expect(
      screen.getByRole("heading", { name: "You’re in, ash." }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: /Sign out/ }));
    expect(await screen.findByLabelText("Username")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("You’re signed out.");
  });

  it("keeps the username on duplicate registration and clears passwords when switching modes", async () => {
    stubFetch(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(signedOut())
        .mockResolvedValueOnce(
          json({ detail: "REGISTER_USER_ALREADY_EXISTS" }, 400),
        ),
    );
    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Create account",
      }),
    );
    await fillCredentials();
    fireEvent.submit(screen.getByLabelText("Username").closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That username is taken.",
    );
    const modeSwitch = screen.getByRole("group", { name: "Account options" });
    await userEvent.click(
      within(modeSwitch).getByRole("button", { name: "Sign in" }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Password", { exact: true })).toHaveValue(
        "",
      ),
    );
    expect(screen.getByLabelText("Username")).toHaveValue("Ash");
  });
});
