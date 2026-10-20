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
    response = await fetch(`/api/${path}`, {
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
    (response.status === 422 && path.startsWith("auth/")) ||
    detail?.code === "REGISTER_INVALID_PASSWORD"
  ) {
    message =
      "Use a username with 3–32 letters, numbers, or underscores and a password with 8–128 characters.";
  } else if (response.status === 401) {
    message =
      "Your session has expired. Sign out and sign in again. Your draft is still here.";
  } else if (response.status === 404) {
    message =
      "This team is no longer available. Your draft is still here; start a new team to save another lineup.";
  } else if (response.status === 422) {
    message =
      detail?.code === "UNKNOWN_POKEMON"
        ? "Some Pokémon are no longer in the catalog. Remove them and try again."
        : "Use a team name of 1–80 characters and no more than six Pokémon.";
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
    return await (await request("auth/me", { signal })).json();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function register(credentials: Credentials): Promise<void> {
  await request("auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
}

export async function login(credentials: Credentials): Promise<User> {
  await request("auth/login", {
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
    await request("auth/logout", { method: "POST" });
  } catch (error) {
    // An expired session is already signed out on the server.
    if (!(error instanceof ApiError && error.status === 401)) throw error;
  }
}

export const pokemonTypes = [
  "normal",
  "fire",
  "water",
  "electric",
  "grass",
  "ice",
  "fighting",
  "poison",
  "ground",
  "flying",
  "psychic",
  "bug",
  "rock",
  "ghost",
  "dragon",
  "dark",
  "steel",
  "fairy",
] as const;
export type Pokemon = {
  id: number;
  name: string;
  types: string[];
  stats: {
    hp: number;
    attack: number;
    defense: number;
    special_attack: number;
    special_defense: number;
    speed: number;
  };
  sprite_url: string | null;
};
export type PokemonPage = {
  items: Pokemon[];
  total: number;
  limit: number;
  offset: number;
};
export type Team = {
  id: string;
  name: string;
  members: { position: number; pokemon: Pokemon }[];
};
export type TeamWrite = { name: string; pokemon_ids: number[] };

export async function getCatalog(
  q: string,
  type: string,
  offset: number,
  signal?: AbortSignal,
): Promise<PokemonPage> {
  const params = new URLSearchParams({
    q,
    limit: "24",
    offset: String(offset),
  });
  if (type) params.set("type", type);
  return (await request(`pokemon?${params}`, { signal })).json();
}
export async function getTeams(signal?: AbortSignal): Promise<Team[]> {
  return (await request("teams", { signal })).json();
}
export async function saveTeam(
  id: string | null,
  draft: TeamWrite,
): Promise<Team> {
  return (
    await request(id ? `teams/${id}` : "teams", {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    })
  ).json();
}
export async function deleteTeam(id: string): Promise<void> {
  await request(`teams/${id}`, { method: "DELETE" });
}
