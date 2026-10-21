import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Profile from "./Profile";
import StatRange from "./StatRange";
import { statNames, StatList, TypeBadge, TypeBadges, Sprite, PokemonCard } from "./PokemonDetails";
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


export default function TeamBuilder({
  user,
  onSignOut,
  signingOut,
  accountError,
  onUserUpdated,
  recoveryVersion = 0,
}: {
  recoveryVersion?: number;
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
  const initialized = useRef(false);
  const pageFocus = useRef<HTMLButtonElement | null>(null);
  const resultsHeading = useRef<HTMLElement>(null);
  const [missingTeam, setMissingTeam] = useState(false);
  const [teamOpen, setTeamOpen] = useState(false);
  const teamDialog = useRef<HTMLDialogElement>(null);
  const teamHost = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const host = teamHost.current!;
    const positionTeam = () => {
      // Tall lineups scroll with the document before their bottom sticks.
      const top = Math.min(16, window.innerHeight - host.getBoundingClientRect().height - 16);
      host.style.setProperty("--team-sticky-top", `${top}px`);
    };
    positionTeam();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(positionTeam) : null;
    observer?.observe(host);
    window.addEventListener("resize", positionTeam);
    return () => { observer?.disconnect(); window.removeEventListener("resize", positionTeam); };
  }, []);
  useEffect(() => {
    if (!teamOpen) return;
    const dialog = teamDialog.current!;
    dialog.showModal();
    return () => dialog.close();
  }, [teamOpen]);
  const [counterSource, setCounterSource] = useState<{
    ids: number[];
    name: string;
  } | null>(null);
  const dirty = signature(name, members) !== baseline;
  const locked = busy || signingOut || teamsLoading || !!teamsError;

  function openTeam(team?: Team) {
    const nextMembers = team ? membersOf(team) : [];
    setMissingTeam(false);
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
          if (!initialized.current) { openTeam(result[0]); initialized.current = true; }
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
  }, [teamsRetry, recoveryVersion]);

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
            // Disabling the paging button can move focus to body in Chromium.
            if (pageFocus.current && (document.activeElement === pageFocus.current || document.activeElement === document.body)) {
              resultsHeading.current?.focus({ preventScroll: true });
              resultsHeading.current?.scrollIntoView?.({ block: "start" });
            }
            pageFocus.current = null;
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
  async function save(asNew = false) {
    if (operation.current || locked || !name.trim()) return;
    operation.current = true;
    setBusy(true);
    setSaveError("");
    setNotice("");
    try {
      const saved = await api.saveTeam(asNew ? null : selected, {
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
      if (error instanceof api.ApiError && error.status === 404 && selected) setMissingTeam(true);
      setSaveError(message(error));
      if (!(error instanceof api.ApiError && error.status === 401)) setTeamOpen(true);
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
  const teamEditor = (
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
              {missingTeam && <button className="quiet-button" disabled={locked || !name.trim()} onClick={() => void save(true)}>Save this lineup as a new team</button>}
              {notice && notice !== "Team saved." && (
                <p className="message success" role="status">
                  {notice}
                </p>
              )}
              <button
                className={`primary-button${notice === "Team saved." && !dirty ? " team-saved" : ""}`}
                aria-live="polite"
                disabled={locked || missingTeam || !name.trim() || (!!selected && !dirty)}
                onClick={() => void save()}
              >
                {busy ? "Working…" : notice === "Team saved." && !dirty ? "Team saved." : "Save team"}
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
  );
  return (
    <main className="builder">
      {header ? createPortal(toolbar, header) : toolbar}
      <h2 className="sr-only trainer-greeting">You’re in, {user.username}.</h2>
      {profileOpen && <Profile user={user} teams={teams} busy={locked} onBack={() => showProfile(false)}
        onEdit={team => { if (canLeave()) { openTeam(team); showProfile(false); setTeamOpen(true); } }}
        onDelete={team => removeTeam(team.id)} onUpdated={next => onUserUpdated?.(next)}
        onPasswordChanged={onSignOut} canEndSession={canLeave} operationError={saveError || teamsError} />}
      {accountError && (
        <p className="message error" role="alert">
          {accountError}
        </p>
      )}
      <button hidden={profileOpen} className="quiet-button mobile-team-entry" onClick={() => setTeamOpen(true)} aria-haspopup="dialog">
        Team · {members.length}/6 · Edit lineup
      </button>
      {teamOpen && teamDialog.current && createPortal(teamEditor, teamDialog.current)}
      <dialog ref={teamDialog} className="team-editor-dialog" aria-label="Edit your team" onCancel={() => setTeamOpen(false)}>
        <button className="quiet-button close-team-editor" onClick={() => setTeamOpen(false)}>Back to browsing</button>
      </dialog>

      <div className="builder-columns" hidden={profileOpen}>
        <section className="catalog-panel" aria-label="Pokémon catalog" id="catalog-title" ref={resultsHeading} tabIndex={-1}>
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
            <summary>
              <span className="filter-label">Filters{types.length || Object.values(ranges).some(Boolean) ? <span className="filter-applied"><span aria-hidden="true">✓</span><span className="sr-only">Filters applied</span></span> : null}</span>
              <span className="catalog-count">{catalog ? `${catalog.total.toLocaleString()} Pokémons found` : "Loading…"}</span>
            </summary>
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
            <p className="sr-only" role="status">{catalogLoading && catalog ? "Updating Pokémon… Showing previous results." : ""}</p>
            {catalogError && <div className="message error" role="alert">{catalogError}{catalog && " Showing previous results."} <button className="quiet-button" onClick={() => setCatalogRetry(value => value + 1)}>Retry catalog</button></div>}
            {!catalog && catalogLoading ? (
              <p className="catalog-state" role="status">
                Loading Pokémon…
              </p>
            ) : !catalog ? null : !catalog.items.length ? (
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
                    <PokemonCard pokemon={pokemon} selectedCount={members.filter(member => member.id === pokemon.id).length} key={pokemon.id}>
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
                    </PokemonCard>
                  ))}
                </div>
                <nav className="catalog-pagination" aria-label="Catalog pages">
                  <button
                    className="quiet-button"
                    disabled={catalogLoading || catalog.offset === 0}
                    onClick={event => { pageFocus.current = event.currentTarget; setOffset(Math.max(0, catalog.offset - pageSize)); }}
                  >
                    Previous
                  </button>
                  <span>
                    {catalog.offset + 1}–
                    {Math.min(catalog.offset + catalog.items.length, catalog.total)} of{" "}
                    {catalog.total}
                  </span>
                  <button
                    className="quiet-button"
                    disabled={catalogLoading || catalog.offset + catalog.limit >= catalog.total}
                    onClick={event => { pageFocus.current = event.currentTarget; setOffset(catalog.offset + pageSize); }}
                  >
                    Next
                  </button>
                </nav>
              </>
            )}
          </div>
        </section>
        <div ref={teamHost} className="team-editor-host">{!teamOpen && teamEditor}</div>
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
