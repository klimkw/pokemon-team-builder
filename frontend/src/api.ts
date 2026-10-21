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
  if (detail?.code === "CURRENT_PASSWORD_INVALID") {
    message = "Current password is incorrect.";
  } else if (detail?.code === "USERNAME_TAKEN") {
    message = "That username is taken.";
  } else if (detail === "REGISTER_USER_ALREADY_EXISTS") {
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
  } else if (
    response.status === 409 &&
    detail?.code === "INSUFFICIENT_CATALOG"
  ) {
    message =
      "The catalog needs more distinct Pokémon to generate a counter of this size.";
  } else if (response.status === 404) {
    message =
      "This team is no longer available. Your draft is still here; start a new team to save another lineup.";
  } else if (response.status === 422 && path === "profile") {
    message = "Use 3–32 letters, numbers or underscores, and an 8–128 character password.";
  } else if (response.status === 422 && path.startsWith("pokemon")) {
    message = "Check your type and stat filters. Minimum must not exceed maximum.";
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
  stat_maxima?: Record<string, number>;
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

export type CatalogOptions = {
  sort?: string;
  types: string[];
  typeMatch: "any" | "all";
  ranges: Record<string, string>;
  limit: number;
};
export async function getCatalog(
  q: string, type: string, offset: number, signal?: AbortSignal,
  options?: CatalogOptions,
): Promise<PokemonPage> {
  const params = new URLSearchParams({ q, limit: String(options?.limit ?? 24), offset: String(offset) });
  if (options?.sort && options.sort !== "index") params.set("sort", options.sort);
  if (type) params.set("type", type);
  options?.types.forEach(value => params.append("types", value));
  if (options?.types.length) params.set("type_match", options.typeMatch);
  Object.entries(options?.ranges ?? {}).forEach(([key, value]) => { if (value !== "") params.set(key, value); });
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

export type Strike = { category: "physical" | "special"; attack_type: string; attack: number; defense: number; effectiveness: number; damage: number };
export type Duel = {
  model_version: string; result: "counter" | "opponent" | "draw" | "stalemate";
  order: "counter" | "opponent" | "simultaneous"; counter_hp: number; opponent_hp: number;
  outgoing: Strike; incoming: Strike;
  turns: { turn: number; counter_hp: number; opponent_hp: number; counter_damage: number; opponent_damage: number }[];
};
export type CounterMatchup = {
  simulation?: Duel | null;
  opponent_position: number;
  opponent: Pokemon;
  counter: Pokemon;
  attacking_type: string;
  incoming_type: string;
  outgoing_multiplier: number;
  incoming_multiplier: number;
  safe: boolean;
  type_strength: number;
  attack_potential: number;
  durability: number;
  speed: number;
  stats_score: number;
};
export type CounterPreview = {
  model_version: string;
  chart_version: string;
  safe_count: number;
  size: number;
  type_strength: number;
  stats_score: number;
  matchups: CounterMatchup[];
};
export async function getCounterPreview(
  pokemonIds: number[],
  signal?: AbortSignal,
): Promise<CounterPreview> {
  return (
    await request("teams/counter-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pokemon_ids: pokemonIds }),
      signal,
    })
  ).json();
}

export type ChangeAlert = {
  history?: Record<string, { id: string; detected_at: string; before: unknown; after: unknown }[]>;
  is_read?: boolean;
  is_manual_demo?: boolean;
  id: string;
  entity_kind: "pokemon" | "type";
  entity_name: string;
  detected_at: string;
  changes: Record<string, { before: unknown; after: unknown }>;
  affected: {
    types: string[];
    id: number;
    name: string;
    reasons: ("catalog" | "attacking_type" | "defending_type")[];
    teams: { id: string; name: string; positions: number[] }[];
  }[];
};
export type AlertPage = {
  unread_total?: number;
  is_demo: boolean;
  items: ChangeAlert[];
  total: number;
  limit: number;
  offset: number;
  window_days: number;
  since: string;
  as_of: string;
  latest_scan: { status: string; started_at: string; finished_at: string | null } | null;
};
export async function getAlerts(offset: number, signal?: AbortSignal): Promise<AlertPage> {
  return (await request(`alerts?limit=10&offset=${offset}`, { signal })).json();
}

export async function markAlertsRead(changeIds: string[]): Promise<void> {
  await request("alerts/read", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ change_ids: changeIds }) });
}
export async function updateProfile(payload: { current_password: string; username?: string; new_password?: string }): Promise<{ user: User; session_revoked: boolean }> {
  return (await request("profile", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).json();
}

export type RefreshStatus = { status: string; started_at: string; finished_at: string | null };
export type AppInfo = {
  app_version: string; counter_model: string; simulation_model: string; repository_url: string;
  catalog_count: number; scan_interval_hours: number; alert_window_days: number;
  latest_live_refresh: RefreshStatus | null; last_successful_live_refresh: RefreshStatus | null; checked_at: string;
};
export async function getAppInfo(signal?: AbortSignal): Promise<AppInfo> {
  return (await request("info", { signal })).json();
}
