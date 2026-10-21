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
  expect(savedButton).toBeDisabled();
  expect(document.querySelector(".team-actions .message.success")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Team name"), { target: { value: "Changed lineup" } });
  expect(screen.getByRole("button", { name: /Save team/ })).toBeEnabled();
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
  expect(within(screen.getByRole("region", { name: "Your team" })).getByText("Saved", { exact: true })).toBeVisible();
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

it("keeps the existing cards mounted during a search update and a failed request", async () => {
  const fetchMock = setup();
  const card = await screen.findByRole("article", { name: "bulbasaur" });
  let finish!: (response: Response) => void;
  fetchMock.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  fireEvent.change(screen.getByLabelText("Search Pokémon"), { target: { value: "pikachu" } });
  expect(screen.getByRole("article", { name: "bulbasaur" })).toBe(card);
  expect(screen.getByText(/Updating Pokémon/)).toBeVisible();
  await waitFor(() => expect(finish).toBeDefined());
  finish(json({}, 500));
  expect(await screen.findByRole("alert")).toHaveTextContent("Showing previous results");
  expect(screen.getByRole("article", { name: "bulbasaur" })).toBe(card);
  expect(screen.getByLabelText("Search Pokémon")).toHaveValue("pikachu");
});

it("opens the persistent editor and keeps edits when returning to browsing", async () => {
  setup([team]);
  await screen.findByLabelText("Team name");
  await userEvent.click(screen.getByRole("button", { name: /Team · 2\/6/ }));
  const editor = screen.getByRole("dialog", { name: "Edit your team" });
  fireEvent.change(within(editor).getByLabelText("Team name"), { target: { value: "Kept draft" } });
  await userEvent.click(within(editor).getByRole("button", { name: "Remove bulbasaur from slot 1" }));
  await userEvent.click(within(editor).getByRole("button", { name: "Back to browsing" }));
  expect(screen.getByLabelText("Team name")).toHaveValue("Kept draft");
  expect(screen.getByRole("button", { name: /Team · 1\/6/ })).toBeVisible();
  expect(screen.getByRole("button", { name: "Remove charmander from slot 1" })).toBeVisible();
});

it("recovers a deleted saved team as a new team with the current ordered draft", async () => {
  const mutate = vi.fn(async (_url: string, init: RequestInit) => init.method === "PUT" ? json({}, 404) : json({ ...team, id: "recovered", name: "Recovered" }));
  setup([team], mutate);
  fireEvent.change(await screen.findByLabelText("Team name"), { target: { value: "Recovered" } });
  await userEvent.click(screen.getByRole("button", { name: /Save team/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Save this lineup as a new team" }));
  await screen.findByText("Team saved.");
  expect(mutate.mock.calls[1][0]).toBe("/api/teams");
  expect(mutate.mock.calls[1][1].method).toBe("POST");
  expect(JSON.parse(String(mutate.mock.calls[1][1].body))).toEqual({ name: "Recovered", pokemon_ids: [1, 4] });
});
