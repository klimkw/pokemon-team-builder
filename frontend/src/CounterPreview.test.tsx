import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "./api";
import CounterPreview from "./CounterPreview";
import type { CounterPreview as Preview, Pokemon, Team } from "./api";

const opponent: Pokemon = {
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
const counter: Pokemon = {
  ...opponent,
  id: 4,
  name: "charmander",
  types: ["fire"],
};
const preview: Preview = {
  chart_version: "sha256:example",
  size: 1,
  safe_count: 1,
  type_strength: 1,
  stats_score: 1500,
  matchups: [
    {
      simulation: {
        result: "counter", order: "simultaneous",
        counter_hp: 45, opponent_hp: 45,
        outgoing: { category: "physical", attack_type: "fire", attack: 49, defense: 49, effectiveness: 2, damage: 60 },
        incoming: { category: "physical", attack_type: "poison", attack: 49, defense: 49, effectiveness: 1, damage: 30 },
        turns: [{ turn: 1, counter_hp: 15, opponent_hp: 0, counter_damage: 60, opponent_damage: 30 }],
      },
      opponent_position: 0,
      opponent,
      counter,
      attacking_type: "fire",
      incoming_type: "poison",
      outgoing_multiplier: 2,
      incoming_multiplier: 1,
      safe: true,
      type_strength: 1,
      attack_potential: 500,
      durability: 500,
      speed: 500,
      stats_score: 1500,
    },
  ],
};
const team: Team = {
  id: "new-counter",
  name: "My counter",
  members: [{ position: 0, pokemon: counter }],
};
const close = vi.fn();
const saved = vi.fn();
const ids = [1];
function show() {
  return render(
    <CounterPreview
      pokemonIds={ids}
      sourceName="My lineup"
      onClose={close}
      onSaved={saved}
    />,
  );
}

beforeEach(() => {
  // jsdom has no native dialog implementation; Chromium E2E tests exercise it.
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(
    function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    },
  );
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (
    this: HTMLDialogElement,
  ) {
    this.removeAttribute("open");
  });
  vi.spyOn(api, "getCounterPreview").mockResolvedValue(preview);
  vi.spyOn(api, "saveTeam").mockResolvedValue(team);
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

it("shows safe coverage, both type directions, and optional stats without saving", async () => {
  show();
  expect(await screen.findByText("1 / 1 safe matchups")).toBeVisible();
  expect(screen.getByText("2× outgoing")).toBeVisible();
  expect(screen.getByText("1× incoming")).toBeVisible();
  expect(api.getCounterPreview).toHaveBeenCalledWith(
    [1],
    expect.any(AbortSignal),
  );
  expect(api.saveTeam).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByText("Compare base stats and tie-break details"),
  );
  expect(screen.getByRole("table")).toBeVisible();
  expect(screen.getByText(/Total: 1500/)).toBeVisible();
});

it("retains the counter name on failed save and permits retry without overwriting the source", async () => {
  vi.mocked(api.saveTeam).mockRejectedValueOnce(
    new Error("Server unavailable"),
  );
  show();
  const name = await screen.findByLabelText("Counter team name");
  fireEvent.change(name, { target: { value: "My counter" } });
  await userEvent.click(
    screen.getByRole("button", { name: /Save as new team/ }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Server unavailable",
  );
  expect(name).toHaveValue("My counter");
  expect(saved).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: /Save as new team/ }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Saved as “My counter”",
  );
  expect(api.saveTeam).toHaveBeenLastCalledWith(null, {
    name: "My counter",
    pokemon_ids: [4],
  });
  expect(saved).toHaveBeenCalledWith(team);
  expect(
    screen.getByRole("button", { name: /Counter team saved/ }),
  ).toBeDisabled();
});

it("shows risky fallback explanations when full safe coverage is impossible", async () => {
  vi.mocked(api.getCounterPreview).mockResolvedValue({
    ...preview,
    safe_count: 0,
    matchups: [
      {
        ...preview.matchups[0],
        safe: false,
        outgoing_multiplier: 1,
        incoming_multiplier: 2,
      },
    ],
  });
  show();
  expect(await screen.findByText("0 / 1 safe matchups")).toBeVisible();
  expect(screen.getByText("Risky type matchup")).toBeVisible();
  expect(screen.getByText(/cannot hit super-effectively/)).toHaveTextContent(
    "The opponent can hit it super-effectively in return.",
  );
});

it("retries failed generation and aborts it when the preview is dismissed", async () => {
  vi.mocked(api.getCounterPreview).mockRejectedValueOnce(
    new Error("Unable to reach server"),
  );
  const view = show();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unable to reach server",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Retry generation" }),
  );
  expect(await screen.findByText("1 / 1 safe matchups")).toBeVisible();
  const signal = vi.mocked(api.getCounterPreview).mock.calls[1][1]!;
  await userEvent.click(screen.getByRole("button", { name: "Close preview" }));
  expect(close).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(signal.aborted).toBe(true);
});

it("blocks duplicate saves and dismissal during an in-flight save", async () => {
  let finish!: (value: Team) => void;
  vi.mocked(api.saveTeam).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  show();
  const button = await screen.findByRole("button", {
    name: /Save as new team/,
  });
  await userEvent.dblClick(button);
  expect(api.saveTeam).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Close preview" })).toBeDisabled();
  fireEvent(
    screen.getByRole("dialog"),
    new Event("cancel", { cancelable: true }),
  );
  expect(close).not.toHaveBeenCalled();
  finish(team);
  await waitFor(() => expect(saved).toHaveBeenCalledWith(team));
});


it("shares Pokédex cards and replays transparent duel results without saving", async () => {
  show();
  await screen.findByText("1 / 1 safe matchups");
  expect(document.querySelectorAll(".paired-cards .pokemon-card")).toHaveLength(2);
  expect(screen.getByRole("link", { name: /Read the scoring/ })).toHaveAttribute("href", "/counter-method");
  await userEvent.click(screen.getByRole("button", { name: "Run matchup simulation" }));
  expect(screen.getByRole("progressbar", { name: "Your slot 1 HP" })).toHaveAttribute("value", "45");
  await userEvent.click(screen.getByRole("button", { name: "Next turn" }));
  expect(screen.getByRole("status")).toHaveTextContent("Counter wins 1 / 1 duels");
  expect(screen.getByRole("progressbar", { name: "Your slot 1 HP" })).toHaveAttribute("value", "0");
  await userEvent.click(screen.getByText("Damage calculation and turn log"));
  expect(screen.getAllByText(/max\(1, floor\(20/)).toHaveLength(2);
  expect(screen.getByText(/Turn 1: counter dealt 60/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Restart simulation" }));
  expect(screen.getByRole("progressbar", { name: "Counter slot 1 HP" })).toHaveAttribute("value", "45");
  expect(api.saveTeam).not.toHaveBeenCalled();
});
