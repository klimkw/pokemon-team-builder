import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Profile from "./Profile";
import StatRange from "./StatRange";
import { statNames, StatList, TypeBadge, TypeBadges } from "./PokemonDetails";
import * as api from "./api";
import CounterPreview from "./CounterPreview";
import Alerts from "./Alerts";
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
  onUserUpdated,
}: {
  onUserUpdated?: (user: User) => void;
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
  const [types, setTypes] = useState<string[]>([]);
  const [typeMatch, setTypeMatch] = useState<"any" | "all">("any");
  const [pageSize, setPageSize] = useState(24);
  const [sort, setSort] = useState("index");
  const [ranges, setRanges] = useState<Record<string, string>>({});
  const [profileOpen, setProfileOpen] = useState(window.location.hash === "#profile");
  useEffect(() => {
    const sync = () => setProfileOpen(window.location.hash === "#profile");
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  function showProfile(open: boolean) {
    setProfileOpen(open);
    window.history.replaceState(null, "", open ? "#profile" : window.location.pathname);
  }
  const invalidRanges = Object.keys(statNames).some(stat => ranges[stat + "_min"] && ranges[stat + "_max"] && Number(ranges[stat + "_min"]) > Number(ranges[stat + "_max"]));
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
    if (invalidRanges) { setCatalogLoading(false); setCatalogError("Minimum must not exceed maximum."); return () => controller.abort(); }
    // Debounce text entry and ignore responses from superseded searches.
    const timer = window.setTimeout(() => {
      api.getCatalog(query.trim(), type, offset, controller.signal, { types, typeMatch, ranges, limit: pageSize, sort }).then(
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
  }, [query, type, types, typeMatch, ranges, pageSize, sort, offset, catalogRetry, invalidRanges]);

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
  async function removeTeam(target = selected) {
    if (!target || operation.current || locked) return;
    if (
      !window.confirm(
        `Delete “${teams.find((team) => team.id === target)?.name ?? name}”? This also discards any unsaved changes to this team.`,
      )
    )
      return;
    operation.current = true;
    setBusy(true);
    setSaveError("");
    setNotice("");
    try {
      await api.deleteTeam(target);
      const remaining = teams.filter((team) => team.id !== target);
      setTeams(remaining);
      if (target === selected) openTeam(remaining[0]);
      setNotice("Team deleted.");
    } catch (error) {
      setSaveError(message(error));
    } finally {
      operation.current = false;
      setBusy(false);
    }
  }

  const membershipKey = JSON.stringify(teams.map(team => [team.id, team.name, team.members.map(member => member.pokemon.id)]));
  const toolbar = <div className="header-actions">
    <Alerts membershipKey={membershipKey} />
    <button className="icon-button" aria-label="Profile" aria-pressed={profileOpen} onClick={() => showProfile(!profileOpen)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></svg>
    </button>
    <button className="quiet-button" disabled={busy || signingOut} onClick={() => { if (canLeave()) void onSignOut(); }}>{signingOut ? "Signing out…" : "Sign out"}</button>
  </div>;
  const header = document.getElementById("workspace-actions");
  return (
    <main className="builder">
      {header ? createPortal(toolbar, header) : toolbar}
      <h2 className="sr-only trainer-greeting">You’re in, {user.username}.</h2>
      {profileOpen && <Profile user={user} teams={teams} busy={locked} onBack={() => showProfile(false)}
        onEdit={team => { if (canLeave()) { openTeam(team); showProfile(false); } }}
        onDelete={team => removeTeam(team.id)} onUpdated={next => onUserUpdated?.(next)}
        onPasswordChanged={onSignOut} canEndSession={canLeave} operationError={saveError || teamsError} />}
      {accountError && (
        <p className="message error" role="alert">
          {accountError}
        </p>
      )}
      <nav hidden={profileOpen} className="builder-jumps" aria-label="Workspace sections">
        <a href="#catalog-title">Browse Pokémon</a>
        <a href="#team-title" onClick={event => { event.preventDefault(); const heading = document.getElementById("team-title"); heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: "start" }); }}>Your team · {members.length} / 6</a>
      </nav>

      <div className="builder-columns" hidden={profileOpen}>
        <section className="catalog-panel" aria-labelledby="catalog-title">
          <div className="panel-heading">
            <div>
              <h1 id="catalog-title">Pokédex</h1>
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
              <label htmlFor="catalog-sort">Sort by</label>
              <select id="catalog-sort" value={sort} onChange={event => { setSort(event.target.value); setOffset(0); }}>
                <option value="index">Index</option>
                {Object.entries(statNames).flatMap(([key, label]) => [<option key={`${key}_asc`} value={`${key}_asc`}>{label} · Low to high</option>, <option key={`${key}_desc`} value={`${key}_desc`}>{label} · High to low</option>])}
              </select>
            </div>
            <div>
              <label htmlFor="page-size">Per page</label>
              <select id="page-size" value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setOffset(0); }}>
                {[12, 24, 48, 96].map(size => <option key={size} value={size}>{size}</option>)}
              </select>
            </div>
          </div>
          <details className="filter-panel">
            <summary>Filters{types.length || Object.values(ranges).some(Boolean) ? " · active" : ""}</summary>
            <fieldset className="type-filter"><legend>Types</legend>
              <div className="type-options">{api.pokemonTypes.map(value => <label className={`type-filter-option ${types.includes(value) ? "selected" : ""}`} key={value}>
                <input type="checkbox" checked={types.includes(value)} onChange={event => { setType(""); setTypes(current => event.target.checked ? [...current, value] : current.filter(t => t !== value)); setOffset(0); }} /><TypeBadge type={value} />
              </label>)}</div>
              <label className="filter-match">Match<select aria-label="Type matching" value={typeMatch} onChange={event => { setTypeMatch(event.target.value as "any" | "all"); setOffset(0); }}><option value="any">Any selected type</option><option value="all">All selected types</option></select></label>
            </fieldset>
            <fieldset><legend>Base stats</legend><div className="stat-ranges">{Object.entries(statNames).map(([key, label]) => {
              const maximum = Math.max(catalog?.stat_maxima?.[key] ?? 255, Number(ranges[`${key}_max`] || 0), Number(ranges[`${key}_min`] || 0));
              return <StatRange key={key} label={label} maximum={maximum} low={Number(ranges[`${key}_min`] || 0)} high={Number(ranges[`${key}_max`] || maximum)}
                onChange={(low, high) => { setRanges(current => ({ ...current, [`${key}_min`]: low === 0 ? "" : String(low), [`${key}_max`]: high === maximum ? "" : String(high) })); setOffset(0); }} />;
            })}</div></fieldset>
            <button className="quiet-button" onClick={() => { setTypes([]); setType(""); setTypeMatch("any"); setRanges({}); setOffset(0); }}>Clear filters</button>
          </details>

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
                  {query || type || types.length || Object.values(ranges).some(Boolean)
                    ? "Try another name or type."
                    : "The catalog hasn’t been loaded yet. Once it’s ready, Pokémon will appear here."}
                </p>
              </div>
            ) : (
              <>
                <div className="pokemon-grid">
                  {catalog.items.map((pokemon) => (
                    <article
                      className={`pokemon-card ${members.some(member => member.id === pokemon.id) ? "is-selected" : ""}`}
                      key={pokemon.id}
                      aria-label={pokemon.name}
                    >
                      <span className="pokemon-number">
                        #{String(pokemon.id).padStart(3, "0")}
                      </span>
                      <Sprite key={pokemon.id} pokemon={pokemon} />
                      <h3>{pokemon.name}</h3>
                      {members.some(member => member.id === pokemon.id) && <span className="selected-label">In team · {members.filter(member => member.id === pokemon.id).length}</span>}
                      <TypeBadges types={pokemon.types} />
                      <StatList pokemon={pokemon} />
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
                      setOffset((value) => Math.max(0, value - pageSize))
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
                    onClick={() => setOffset((value) => value + pageSize)}
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
              <h2 id="team-title" tabIndex={-1}>Your team</h2>
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
                    <option value="">
                      Draft a New Team
                    </option>
                    {teams.map((team) => (
                      <option key={team.id} value={team.id}>
                        {team.name}
                      </option>
                    ))}
                  </select>
                </div>
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
                      ? "Saved"
                      : "New team draft"}
                </span>

              </div>

              <ol className="team-members" aria-label="Selected Pokémon">
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
                            <TypeBadges types={pokemon.types} />
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
                          <StatList pokemon={pokemon} className="member-stats" />
                        </>
                      ) : (
                        <span>Empty slot</span>
                      )}
                    </li>
                  );
                })}
              </ol>
              <div className="team-actions">
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
              </div>


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
