import { useEffect, useRef, useState } from "react";
import { PokemonCard } from "./PokemonDetails";
import BattleReplay from "./BattleReplay";
import * as api from "./api";
import type { CounterPreview as Preview, Team } from "./api";

const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
const baseStats = [
  ["hp", "HP"],
  ["attack", "Attack"],
  ["defense", "Defense"],
  ["special_attack", "Sp. Atk"],
  ["special_defense", "Sp. Def"],
  ["speed", "Speed"],
] as const;

export default function CounterPreview({
  pokemonIds,
  sourceName,
  onClose,
  onSaved,
}: {
  pokemonIds: number[];
  sourceName: string;
  onClose: () => void;
  onSaved: (team: Team) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const savingRef = useRef(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const [name, setName] = useState(
    `Counter to ${sourceName.trim() || "my lineup"}`.slice(0, 80),
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    closeButton.current?.focus();
    return () => element.close();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    api.getCounterPreview(pokemonIds, controller.signal).then(
      (result) => {
        if (!controller.signal.aborted) {
          setPreview(result);
          setLoading(false);
        }
      },
      (error) => {
        if (!controller.signal.aborted) {
          setError(errorMessage(error));
          setLoading(false);
        }
      },
    );
    return () => controller.abort();
  }, [pokemonIds, retry]);

  async function save() {
    if (!preview || !name.trim() || savingRef.current || saved) return;
    savingRef.current = true;
    setSaving(true);
    setError("");
    try {
      const team = await api.saveTeam(null, {
        name: name.trim(),
        pokemon_ids: preview.matchups.map((match) => match.counter.id),
      });
      setName(team.name);
      setSaved(true);
      onSaved(team);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="counter-dialog"
      aria-labelledby="counter-title"
      aria-describedby="counter-description"
      onCancel={(event) => {
        event.preventDefault();
        if (!savingRef.current) onClose();
      }}
    >
      <div className="counter-heading">
        <div>
          <h2 id="counter-title">Optimal counter team</h2>
        </div>
        <button
          ref={closeButton}
          className="quiet-button"
          disabled={saving}
          onClick={onClose}
        >
          Close preview
        </button>
      </div>
      <p id="counter-description" className="counter-description">
        Based on your current draft. Saved as a separate team.
      </p>
      {loading && (
        <p role="status" className="catalog-state">
          Finding the best counter lineup…
        </p>
      )}
      {error && (
        <p role="alert" className="message error">
          {error}
        </p>
      )}
      {!loading && !preview && (
        <button
          className="quiet-button"
          onClick={() => setRetry((value) => value + 1)}
        >
          Retry generation
        </button>
      )}
      {preview && (
        <>
          <div className="counter-summary">
            <strong>
              {preview.safe_count} / {preview.size} safe matchups
            </strong>
            <p>
              {preview.safe_count === preview.size
                ? "Every opposing slot has a counter that can hit super-effectively without taking super-effective damage back."
                : "This is the best safe coverage available under this model. Some pairings still involve a trade-off; review their details below."}
            </p>
          </div>
          <p className="counter-model-link"><a href="/counter-method" target="_blank" rel="noreferrer">Read the scoring & simulation guide ↗</a><button className="quiet-button" onClick={() => { const heading = document.getElementById("simulation-title"); heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: "start" }); }}>Go to simulation ↓</button></p>
          <p className="model-objective">Type strength: {preview.type_strength} · Stats tie-break: {preview.stats_score} / {preview.size * 3000}</p>
          <details className="counter-method">
            <summary>How we choose the optimal team</summary>
            <ol>
              <li>
                Maximize safe matchups: at least 2× outgoing effectiveness and
                at most 1× incoming.
              </li>
              <li>
                Then maximize the sum of outgoing minus incoming effectiveness
                across the lineup.
              </li>
              <li>
                Then compare relative attack potential, durability, and speed.
                Equal results use a consistent Pokémon ID tie-break.
              </li>
            </ol>
            <p>
              Each member is paired with one opposing slot, using distinct
              catalog Pokémon. All catalog entries, including special forms and
              legendary Pokémon, are eligible. Slot pairing explains coverage;
              it does not simulate battle order.
            </p>
            <p>
              We assume both sides can use an attack of either of their own
              types. Each uses its best type against the other's full typing.
              Moves, abilities, items, levels, and switching are not simulated.
              Multipliers describe type effectiveness, not predicted damage or
              win probability.
            </p>
            <p>
              Stats score: attack potential compares Attack against Defense and
              Sp. Atk against Sp. Def, taking the better relative advantage.
              Durability compares HP × Defense against opposing HP × Attack for
              both physical and special attacks, then averages the two. Speed
              compares base Speed. Each component is scaled to 0–1,000 and
              summed; stats only break ties in the first two priorities.
            </p>
          </details>
          <ol className="counter-matchups">
            {preview.matchups.map((match) => (
              <li key={match.opponent_position} className="counter-matchup">
                <div className="counter-pair-heading">
                  <span className="eyebrow">
                    OPPOSING SLOT {match.opponent_position + 1}
                  </span>
                  <span
                    className={`matchup-label ${match.safe ? "safe" : "risky"}`}
                  >
                    {match.safe ? "Safe type matchup" : "Risky type matchup"}
                  </span>
                </div>
                <div className="paired-cards">
                  <div><p className="pair-side-label">Your Pokémon</p><PokemonCard pokemon={match.opponent} /></div>
                  <div><p className="pair-side-label">Counter</p><PokemonCard pokemon={match.counter} /></div>
                </div>
                <div className="matchup-effects">
                  <p>
                    <span>Your Pokémon → counter</span>
                    <strong>{match.incoming_multiplier}× incoming</strong>
                    <span>Opponent’s best assumed attack: {match.incoming_type} against {match.counter.types.join(" / ")}.</span>
                  </p>
                  <p>
                    <span>Counter → your Pokémon</span>
                    <strong>{match.outgoing_multiplier}× outgoing</strong>
                    <span>Using {match.attacking_type} against {match.opponent.types.join(" / ")}.</span>
                  </p>
                </div>
                {!match.safe && (
                  <p className="matchup-caution">
                    {match.outgoing_multiplier < 2
                      ? "This counter cannot hit super-effectively with its own types. "
                      : ""}
                    {match.incoming_multiplier > 1
                      ? "The opponent can hit it super-effectively in return."
                      : ""}
                  </p>
                )}
                <details className="matchup-stats">
                  <summary>Compare base stats and tie-break details</summary>
                  <table>
                    <caption>
                      Base stats: {match.counter.name} versus{" "}
                      {match.opponent.name}
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Stat</th>
                        <th scope="col">Counter</th>
                        <th scope="col">Opponent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {baseStats.map(([key, label]) => (
                        <tr key={key}>
                          <th scope="row">{label}</th>
                          <td>{match.counter.stats[key]}</td>
                          <td>{match.opponent.stats[key]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p>
                    Attack potential {match.attack_potential} · Durability{" "}
                    {match.durability} · Speed {match.speed}. Total:{" "}
                    {match.stats_score} / 3,000. These contribute only after
                    safe coverage and type strength tie.
                  </p>
                </details>
              </li>
            ))}
          </ol>
          <BattleReplay matches={preview.matchups} />
          <details className="model-versions"><summary>Model & data versions</summary><p>Selection: {preview.model_version}</p><p>Type chart: {preview.chart_version}</p></details>
          <div className="counter-save">
            <label htmlFor="counter-name">Counter team name</label>
            <input
              id="counter-name"
              value={name}
              maxLength={80}
              disabled={saving || saved}
              onChange={(event) => setName(event.target.value)}
            />
            <button
              className="primary-button"
              disabled={saving || saved || !name.trim()}
              onClick={() => void save()}
            >
              {saved
                ? "Counter team saved"
                : saving
                  ? "Saving counter team…"
                  : "Save as new team"}
              <span aria-hidden="true">↗</span>
            </button>
            {saved ? (
              <p className="message success" role="status">
                Saved as “{name}”. You can select it from Saved teams after
                closing this preview. Your original lineup is unchanged.
              </p>
            ) : (
              <p className="save-hint">
                This preview is not saved until you choose Save as new team.
              </p>
            )}
            <button className="secondary-button" disabled={saving} onClick={onClose}>Back to lineup</button>
          </div>
        </>
      )}
    </dialog>
  );
}
