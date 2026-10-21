import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import TeamBuilder from "./TeamBuilder";
import type { Pokemon, Team } from "./api";

const bulbasaur: Pokemon = {
  id: 1,
  name: "bulbasaur",
  types: ["grass", "poison"],
  sprite_url: null,
  stats: {
    hp: 45,
    attack: 49,
    defense: 49,
    special_attack: 65,
    special_defense: 65,
    speed: 45,
  },
};
const charmander: Pokemon = {
  ...bulbasaur,
  id: 4,
  name: "charmander",
  types: ["fire"],
};
const team: Team = {
  id: "saved-team",
  name: "First lineup",
  members: [
    { position: 0, pokemon: bulbasaur },
    { position: 1, pokemon: charmander },
  ],
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const onSignOut = vi.fn().mockResolvedValue(undefined);
function setup(
  teams: Team[] = [],
  mutate?: (url: string, init: RequestInit) => Promise<Response>,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (init.method)
        return mutate
          ? mutate(url, init)
          : json({ ...team, ...JSON.parse(String(init.body)), members: [] });
      if (url.startsWith("/api/alerts?")) return json({ items: [], total: 0, limit: 10, offset: 0, window_days: 7, latest_scan: null });
      if (url === "/api/teams") return json(teams);
      return json({
        items: [bulbasaur, charmander],
        total: 2,
        limit: 24,
        offset: 0,
      });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  render(
    <TeamBuilder
      user={{ id: "user", username: "ash" }}
      onSignOut={onSignOut}
      signingOut={false}
      accountError=""
    />,
  );
  return fetchMock;
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("caps a duplicate-friendly draft at six and saves its ordered IDs", async () => {
  const mutate = vi.fn(async (_url: string, _init: RequestInit) =>
    json({
      ...team,
      name: "Six partners",
      members: Array.from({ length: 6 }, (_, position) => ({
        position,
        pokemon: bulbasaur,
      })),
    }),
  );
  setup([], mutate);
  const browser = userEvent.setup();
  const add = await screen.findByRole("button", {
    name: "Add bulbasaur to team",
  });
  for (let i = 0; i < 6; i++) await browser.click(add);
  expect(add).toBeDisabled();
  expect(screen.getByText("6 / 6")).toBeVisible();
  await browser.type(screen.getByLabelText("Team name"), "Six partners");
  await browser.click(screen.getByRole("button", { name: /Save team/ }));
  const savedButton = await screen.findByRole("button", { name: "Team saved." });
  expect(savedButton).toHaveClass("team-saved");
  expect(savedButton).toBeDisabled();
  expect(document.querySelector(".team-actions .message.success")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Team name"), { target: { value: "Changed lineup" } });
  expect(screen.getByRole("button", { name: /Save team/ })).not.toHaveClass("team-saved");
  expect(JSON.parse(mutate.mock.calls[0][1].body as string)).toEqual({
    name: "Six partners",
    pokemon_ids: [1, 1, 1, 1, 1, 1],
  });
  expect(mutate.mock.calls[0][1].method).toBe("POST");
});

it("reorders a saved team and preserves the edited draft after a failed save", async () => {
  const mutate = vi.fn(async (_url: string, _init: RequestInit) =>
    json({}, 500),
  );
  setup([team], mutate);
  await userEvent.click(
    await screen.findByRole("button", { name: "Move charmander in slot 2 up" }),
  );
  await userEvent.click(screen.getByRole("button", { name: /Save team/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "server is unavailable",
  );
  expect(
    screen.getByRole("button", { name: "Remove charmander from slot 1" }),
  ).toBeEnabled();
  expect(screen.getByText("Unsaved changes")).toBeVisible();
  expect(
    JSON.parse(mutate.mock.calls[0][1].body as string).pokemon_ids,
  ).toEqual([4, 1]);
  expect(mutate.mock.calls[0][1].method).toBe("PUT");
});

it("keeps edits when discard is cancelled and permits switching when confirmed", async () => {
  const second = { ...team, id: "second", name: "Second lineup" };
  setup([team, second]);
  const input = await screen.findByLabelText("Team name");
  await waitFor(() => expect(input).toHaveValue("First lineup"));
  fireEvent.change(input, { target: { value: "Edited" } });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.change(screen.getByLabelText("Saved teams"), {
    target: { value: "second" },
  });
  expect(input).toHaveValue("Edited");
  expect(screen.getByLabelText("Saved teams")).toHaveValue("saved-team");
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(onSignOut).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  fireEvent.change(screen.getByLabelText("Saved teams"), {
    target: { value: "second" },
  });
  expect(input).toHaveValue("Second lineup");
  expect(screen.getByText("Saved", { exact: true })).toBeVisible();
});

it("confirms deletion and selects the remaining saved team", async () => {
  const mutate = vi.fn(
    async (_url: string, _init: RequestInit) =>
      new Response(null, { status: 204 }),
  );
  setup([team, { ...team, id: "second", name: "Second lineup" }], mutate);
  const remove = await screen.findByRole("button", { name: "Delete team" });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  await userEvent.click(remove);
  expect(mutate).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  await userEvent.click(remove);
  expect(await screen.findByText("Team deleted.")).toBeVisible();
  expect(screen.getByLabelText("Team name")).toHaveValue("Second lineup");
  expect(mutate.mock.calls[0][1].method).toBe("DELETE");
});

it("saves an empty team and blocks duplicate submissions while saving", async () => {
  let finish!: (response: Response) => void;
  const mutate = vi.fn(
    (_url: string, _init: RequestInit) =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  setup([], mutate);
  const input = await screen.findByLabelText("Team name");
  fireEvent.change(input, { target: { value: "Empty lineup" } });
  const save = screen.getByRole("button", { name: /Save team/ });
  await userEvent.dblClick(save);
  expect(mutate).toHaveBeenCalledTimes(1);
  expect(input).toBeDisabled();
  expect(
    JSON.parse(mutate.mock.calls[0][1].body as string).pokemon_ids,
  ).toEqual([]);
  finish(json({ ...team, name: "Empty lineup", members: [] }));
  expect(await screen.findByText("Team saved.")).toBeVisible();
});

it("sends search and type filters, resets pagination, and shows all six stats", async () => {
  const fetchMock = setup();
  const card = await screen.findByRole("article", { name: "bulbasaur" });
  for (const label of [
    "HP",
    "Attack",
    "Defense",
    "Sp. Atk",
    "Sp. Def",
    "Speed",
  ])
    expect(within(card).getByText(label)).toBeVisible();
  fireEvent.change(screen.getByLabelText("Search Pokémon"), {
    target: { value: "bulb" },
  });
  fireEvent.click(screen.getByText(/^Filters/));
  fireEvent.click(screen.getByRole("checkbox", { name: "grass" }));
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("q=bulb&limit=24&offset=0&types=grass"),
      ),
    ).toBe(true),
  );
});
