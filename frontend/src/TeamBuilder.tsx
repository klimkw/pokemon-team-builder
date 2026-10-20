import { useEffect, useRef, useState } from "react";
import * as api from "./api";
import CounterPreview from "./CounterPreview";
import type { Pokemon, PokemonPage, Team, User } from "./api";

const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
const membersOf = (team: Team) =>
  [...team.members]
    .sort((a, b) => a.position - b.position)
    .map((member) => member.pokemon);
const signature = (name: string, members: Pokemon[]) =>
  JSON.stringify([name, members.map((pokemon) => pokemon.id)]);
const statNames: Record<keyof Pokemon["stats"], string> = {
  hp: "HP",
  attack: "Attack",
  defense: "Defense",
  special_attack: "Sp. Atk",
  special_defense: "Sp. Def",
  speed: "Speed",
};

function Sprite({ pokemon }: { pokemon: Pokemon }) {
  const [failed, setFailed] = useState(false);
  return pokemon.sprite_url && !failed ? (
    <img
      className="pokemon-sprite"
      src={pokemon.sprite_url}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  ) : (
    <span className="sprite-placeholder" aria-label="Sprite unavailable">
      ◇
    </span>
  );
}

export default function TeamBuilder({
  user,
  onSignOut,
  signingOut,
  accountError,
}: {
  user: User;
  onSignOut: () => Promise<void>;
  signingOut: boolean;
  accountError: string;
}) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(true);
  const [teamsError, setTeamsError] = useState("");
  const [teamsRetry, setTeamsRetry] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [members, setMembers] = useState<Pokemon[]>([]);
  const [baseline, setBaseline] = useState(signature("", []));
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [offset, setOffset] = useState(0);
  const [catalog, setCatalog] = useState<PokemonPage | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [catalogRetry, setCatalogRetry] = useState(0);
  const operation = useRef(false);
  const [counterSource, setCounterSource] = useState<{
    ids: number[];
    name: string;
  } | null>(null);
  const dirty = signature(name, members) !== baseline;
  const locked = busy || signingOut || teamsLoading || !!teamsError;

  function openTeam(team?: Team) {
    const nextMembers = team ? membersOf(team) : [];
    setSelected(team?.id ?? null);
    setName(team?.name ?? "");
    setMembers(nextMembers);
    setBaseline(signature(team?.name ?? "", nextMembers));
    setSaveError("");
    setNotice("");
  }

  useEffect(() => {
    const controller = new AbortController();
    setTeamsLoading(true);
    setTeamsError("");
    api.getTeams(controller.signal).then(
      (result) => {
        if (!controller.signal.aborted) {
          setTeams(result);
          openTeam(result[0]);
          setTeamsLoading(false);
        }
      },
      (error) => {
        if (!controller.signal.aborted) {
          setTeamsError(message(error));
          setTeamsLoading(false);
        }
      },
    );
    return () => controller.abort();
  }, [teamsRetry]);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogLoading(true);
    setCatalogError("");
    // Debounce text entry and ignore responses from superseded searches.
    const timer = window.setTimeout(() => {
      api.getCatalog(query.trim(), type, offset, controller.signal).then(
        (result) => {
          if (!controller.signal.aborted) {
            setCatalog(result);
            setCatalogLoading(false);
          }
        },
        (error) => {
          if (!controller.signal.aborted) {
            setCatalogError(message(error));
            setCatalogLoading(false);
          }
        },
      );
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, type, offset, catalogRetry]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function canLeave() {
    return !dirty || window.confirm("Discard your unsaved team changes?");
  }
  function changeDraft(next: Pokemon[]) {
    setMembers(next);
    setNotice("");
    setSaveError("");
  }
  function move(index: number, delta: number) {
    const next = [...members];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    changeDraft(next);
  }
  async function save() {
    if (operation.current || locked || !name.trim()) return;
    operation.current = true;
    setBusy(true);
    setSaveError("");
    setNotice("");
    try {
      const saved = await api.saveTeam(selected, {
        name: name.trim(),
        pokemon_ids: members.map((pokemon) => pokemon.id),
      });
      setTeams((current) => [
        saved,
        ...current.filter((team) => team.id !== saved.id),
      ]);
      openTeam(saved);
      setNotice("Team saved.");
    } catch (error) {
      setSaveError(message(error));
    } finally {
      operation.current = false;
      setBusy(false);
    }
  }
  async function removeTeam() {
    if (!selected || operation.current || locked) return;
    if (
      !window.confirm(
        `Delete “${teams.find((team) => team.id === selected)?.name ?? name}”? This also discards any unsaved changes to this team.`,
      )
    )
      return;
    operation.current = true;
    setBusy(true);
    setSaveError("");
    setNotice("");
    try {
      await api.deleteTeam(selected);
      const remaining = teams.filter((team) => team.id !== selected);
      setTeams(remaining);
      openTeam(remaining[0]);
      setNotice("Team deleted.");
    } catch (error) {
      setSaveError(message(error));
    } finally {
      operation.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="builder">
      <div className="builder-heading">
        <div>
          <p className="eyebrow">YOUR NEXT LINEUP</p>
          <h1>
            Make room for <span>possibility.</span>
          </h1>
          <h2 className="trainer-greeting">You’re in, {user.username}.</h2>
        </div>
        <button
          className="quiet-button"
          disabled={busy || signingOut}
          onClick={() => {
            if (canLeave()) void onSignOut();
          }}
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </div>
      {accountError && (
        <p className="message error" role="alert">
          {accountError}
        </p>
      )}
      <nav className="builder-jumps" aria-label="Workspace sections">
        <a href="#catalog-title">Browse Pokémon</a>
        <a href="#team-title">Your team · {members.length} / 6</a>
      </nav>
      <div className="builder-columns">
        <section className="catalog-panel" aria-labelledby="catalog-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">FIND YOUR PARTNERS</p>
              <h2 id="catalog-title">The Pokédex</h2>
            </div>
            <span className="catalog-count">
              {catalog && !catalogLoading && !catalogError
                ? `${catalog.total} Pokémon`
                : "Explore the catalog"}
            </span>
          </div>
          <div className="catalog-filters">
            <div>
              <label htmlFor="pokemon-search">Search Pokémon</label>
              <input
                id="pokemon-search"
                type="search"
                maxLength={100}
                placeholder="Try Bulbasaur…"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setOffset(0);
                }}
              />
            </div>
            <div>
              <label htmlFor="pokemon-type">Type</label>
              <select
                id="pokemon-type"
                value={type}
                onChange={(event) => {
                  setType(event.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All types</option>
                {api.pokemonTypes.map((value) => (
                  <option key={value} value={value}>
                    {value[0].toUpperCase() + value.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div aria-busy={catalogLoading}>
            {catalogLoading ? (
              <p className="catalog-state" role="status">
                Loading Pokémon…
              </p>
            ) : catalogError ? (
              <div className="catalog-state">
                <p role="alert">{catalogError}</p>
                <button
                  className="quiet-button"
                  onClick={() => setCatalogRetry((value) => value + 1)}
                >
                  Retry catalog
                </button>
              </div>
            ) : !catalog?.items.length ? (
              <div className="catalog-state">
                <h3>No Pokémon to show</h3>
                <p>
                  {query || type
                    ? "Try another name or type."
                    : "The catalog hasn’t been loaded yet. Once it’s ready, Pokémon will appear here."}
                </p>
              </div>
            ) : (
              <>
                <div className="pokemon-grid">
                  {catalog.items.map((pokemon) => (
                    <article
                      className="pokemon-card"
                      key={pokemon.id}
                      aria-label={pokemon.name}
                    >
                      <span className="pokemon-number">
                        #{String(pokemon.id).padStart(3, "0")}
                      </span>
                      <Sprite key={pokemon.id} pokemon={pokemon} />
                      <h3>{pokemon.name}</h3>
                      <div className="type-badges">
                        {pokemon.types.map((value) => (
                          <span
                            className={`type-badge type-${value}`}
                            key={value}
                          >
                            {value}
                          </span>
                        ))}
                      </div>
                      <dl className="pokemon-stats">
                        {(
                          Object.keys(statNames) as (keyof Pokemon["stats"])[]
                        ).map((key) => (
                          <div key={key}>
                            <dt>{statNames[key]}</dt>
                            <dd>{pokemon.stats[key]}</dd>
                          </div>
                        ))}
                      </dl>
                      <button
                        className="add-button"
                        disabled={locked || members.length >= 6}
                        onClick={() => {
                          if (members.length < 6)
                            changeDraft([...members, pokemon]);
                        }}
                        aria-label={`Add ${pokemon.name} to team`}
                      >
                        {members.length >= 6 ? "Team full" : "Add to team"}
                        <span aria-hidden="true">+</span>
                      </button>
                    </article>
                  ))}
                </div>
                <nav className="catalog-pagination" aria-label="Catalog pages">
                  <button
                    className="quiet-button"
                    disabled={offset === 0}
                    onClick={() =>
                      setOffset((value) => Math.max(0, value - 24))
                    }
                  >
                    Previous
                  </button>
                  <span>
                    {offset + 1}–
                    {Math.min(offset + catalog.items.length, catalog.total)} of{" "}
                    {catalog.total}
                  </span>
                  <button
                    className="quiet-button"
                    disabled={offset + catalog.limit >= catalog.total}
                    onClick={() => setOffset((value) => value + 24)}
                  >
                    Next
                  </button>
                </nav>
              </>
            )}
          </div>
        </section>
        <section
          className="team-panel"
          aria-labelledby="team-title"
          aria-busy={busy || teamsLoading}
        >
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SIX SPOTS. YOUR CALL.</p>
              <h2 id="team-title">Your team</h2>
            </div>
            <span className="member-count">{members.length} / 6</span>
          </div>
          {teamsLoading ? (
            <p className="catalog-state" role="status">
              Loading your teams…
            </p>
          ) : teamsError ? (
            <div className="catalog-state">
              <p role="alert">{teamsError}</p>
              <button
                className="quiet-button"
                onClick={() => setTeamsRetry((value) => value + 1)}
              >
                Retry teams
              </button>
            </div>
          ) : (
            <>
              <div className="team-picker">
                <div>
                  <label htmlFor="saved-team">Saved teams</label>
                  <select
                    id="saved-team"
                    value={selected ?? ""}
                    disabled={locked}
                    onChange={(event) => {
                      if (canLeave())
                        openTeam(
                          teams.find((team) => team.id === event.target.value),
                        );
                    }}
                  >
                    <option value="" disabled>
                      New team draft
                    </option>
                    {teams.map((team) => (
                      <option key={team.id} value={team.id}>
                        {team.name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  className="quiet-button"
                  disabled={locked}
                  onClick={() => {
                    if (canLeave()) openTeam();
                  }}
                >
                  New team
                </button>
              </div>
              <label htmlFor="team-name">Team name</label>
              <input
                id="team-name"
                placeholder="Give your lineup a name"
                maxLength={80}
                value={name}
                disabled={locked}
                onChange={(event) => {
                  setName(event.target.value);
                  setNotice("");
                  setSaveError("");
                }}
              />
              <div className="draft-caption">
                <span>
                  {dirty
                    ? "Unsaved changes"
                    : selected
                      ? "All changes saved"
                      : "New team draft"}
                </span>
                <span>Duplicates welcome</span>
              </div>
              <ol className="team-members">
                {Array.from({ length: 6 }, (_, index) => {
                  const pokemon = members[index];
                  return (
                    <li
                      className={
                        pokemon ? "team-member" : "team-member empty-member"
                      }
                      key={index}
                    >
                      <span className="slot-number">0{index + 1}</span>
                      {pokemon ? (
                        <>
                          <Sprite key={pokemon.id} pokemon={pokemon} />
                          <div className="member-info">
                            <h3>{pokemon.name}</h3>
                            <span>{pokemon.types.join(" / ")}</span>
                          </div>
                          <div className="member-actions">
                            <button
                              disabled={locked || index === 0}
                              aria-label={`Move ${pokemon.name} in slot ${index + 1} up`}
                              onClick={() => move(index, -1)}
                            >
                              ↑
                            </button>
                            <button
                              disabled={locked || index === members.length - 1}
                              aria-label={`Move ${pokemon.name} in slot ${index + 1} down`}
                              onClick={() => move(index, 1)}
                            >
                              ↓
                            </button>
                            <button
                              disabled={locked}
                              aria-label={`Remove ${pokemon.name} from slot ${index + 1}`}
                              onClick={() =>
                                changeDraft(
                                  members.filter(
                                    (_, position) => position !== index,
                                  ),
                                )
                              }
                            >
                              ×
                            </button>
                          </div>
                        </>
                      ) : (
                        <span>Choose a Pokémon from the catalog</span>
                      )}
                    </li>
                  );
                })}
              </ol>
              <p className="team-hint">
                Order matters. Use the arrows to arrange your lineup.
              </p>
              {saveError && (
                <p className="message error" role="alert">
                  {saveError}
                </p>
              )}
              {notice && (
                <p className="message success" role="status">
                  {notice}
                </p>
              )}
              <button
                className="primary-button"
                disabled={locked || !name.trim() || (!!selected && !dirty)}
                onClick={() => void save()}
              >
                {busy ? "Working…" : "Save team"}
                <span aria-hidden="true">↗</span>
              </button>
              <p className="save-hint">
                Changes are saved only when you choose Save team.
              </p>
              <div className="counter-entry">
                <button
                  className="secondary-button"
                  disabled={locked || members.length === 0}
                  onClick={() =>
                    setCounterSource({
                      ids: members.map((pokemon) => pokemon.id),
                      name,
                    })
                  }
                >
                  View optimal counter team <span aria-hidden="true">↗</span>
                </button>
                <p className="save-hint">
                  {members.length
                    ? "Preview counters for this lineup. No save required."
                    : "Add at least one Pokémon to view a counter team."}
                </p>
              </div>
              {selected && (
                <button
                  className="delete-team"
                  disabled={locked}
                  onClick={() => void removeTeam()}
                >
                  Delete team
                </button>
              )}
            </>
          )}
        </section>
      </div>
      {counterSource && (
        <CounterPreview
          pokemonIds={counterSource.ids}
          sourceName={counterSource.name}
          onClose={() => setCounterSource(null)}
          onSaved={(team) =>
            setTeams((current) => [
              team,
              ...current.filter((item) => item.id !== team.id),
            ])
          }
        />
      )}
    </main>
  );
}
