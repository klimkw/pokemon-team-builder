export type User = { id: string; username: string };
export type Credentials = { username: string; password: string };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`/api/auth/${path}`, {
      ...init,
      credentials: "same-origin",
      cache: "no-store",
      signal: init.signal
        ? AbortSignal.any([init.signal, AbortSignal.timeout(15_000)])
        : AbortSignal.timeout(15_000),
    });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(0, "Unable to reach the server. Please try again.");
  }

  if (response.ok) return response;

  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  let message = "Something went wrong. Please try again.";
  if (detail === "REGISTER_USER_ALREADY_EXISTS") {
    message = "That username is taken. Try another or sign in.";
  } else if (detail === "LOGIN_BAD_CREDENTIALS") {
    message = "Username or password is incorrect.";
  } else if (
    response.status === 422 ||
    detail?.code === "REGISTER_INVALID_PASSWORD"
  ) {
    message =
      "Use a username with 3–32 letters, numbers, or underscores and a password with 8–128 characters.";
  } else if (response.status === 403) {
    message = "This request was blocked. Refresh the page and try again.";
  } else if (response.status >= 500) {
    message = "The server is unavailable. Please try again shortly.";
  }
  throw new ApiError(response.status, message);
}

export async function getCurrentUser(
  signal?: AbortSignal,
): Promise<User | null> {
  try {
    return await (await request("me", { signal })).json();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function register(credentials: Credentials): Promise<void> {
  await request("register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
}

export async function login(credentials: Credentials): Promise<User> {
  await request("login", {
    method: "POST",
    body: new URLSearchParams(credentials),
  });
  const user = await getCurrentUser();
  if (!user)
    throw new ApiError(
      401,
      "Your session could not be started. Check that cookies are enabled and try again.",
    );
  return user;
}

export async function logout(): Promise<void> {
  try {
    await request("logout", { method: "POST" });
  } catch (error) {
    // An expired session is already signed out on the server.
    if (!(error instanceof ApiError && error.status === 401)) throw error;
  }
}
