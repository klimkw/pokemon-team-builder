import { useState } from "react";
import type { CounterMatchup, Strike } from "./api";

function Formula({ strike, label }: { strike: Strike; label: string }) {
  return <p><strong>{label} · {strike.category} · {strike.attack_type}</strong><br />
    {strike.effectiveness === 0 ? "Immune: 0 damage" : `max(1, floor(20 × ${strike.attack} / ${strike.defense} × 1.5 × ${strike.effectiveness})) = ${strike.damage} damage`}
  </p>;
}

export default function BattleReplay({ matches }: { matches: CounterMatchup[] }) {
  const [turn, setTurn] = useState<number | null>(null);
  const ready = matches.every(match => match.simulation);
  const maxTurns = Math.max(0, ...matches.map(match => match.simulation?.turns.length ?? 0));
  const finished = turn !== null && turn >= maxTurns;
  const count = (result: string) => matches.filter(match => match.simulation?.result === result).length;
  return <section className="battle-replay" aria-labelledby="simulation-title">
    <h3 id="simulation-title" tabIndex={-1}>Matchup simulation</h3>
    <p>Independent paired duels using base stats and equal-power attacks. No switching, movesets, abilities, items or randomness. These results are not a real battle win rate.</p>
    {turn === null ? <button className="secondary-button" disabled={!ready} onClick={() => setTurn(0)}>Run matchup simulation</button> : <>
      <div className="replay-controls">
        <button className="quiet-button" disabled={finished} onClick={() => setTurn(value => (value ?? 0) + 1)}>Next turn</button>
        <button className="quiet-button" disabled={finished} onClick={() => setTurn(maxTurns)}>Show result</button>
        <button className="quiet-button" onClick={() => setTurn(0)}>Restart simulation</button>
      </div>
      <p role="status">{finished ? `Counter wins ${count("counter")} / ${matches.length} duels · Your wins ${count("opponent")} · Draws ${count("draw")} · Stalemates ${count("stalemate")}` : `Turn ${turn} · ${maxTurns} maximum in this replay`}</p>
      <ol className="duel-results">{matches.map(match => {
        const duel = match.simulation!;
        const state = duel.turns[Math.min(turn, duel.turns.length) - 1];
        const chp = state?.counter_hp ?? duel.counter_hp;
        const ohp = state?.opponent_hp ?? duel.opponent_hp;
        const done = turn >= duel.turns.length;
        return <li key={match.opponent_position}>
          <h4>Slot {match.opponent_position + 1} · <span className="pokemon-name">{match.opponent.name} vs {match.counter.name}</span></h4>
          <div className="duel-health">
            <label>Your Pokémon · {ohp} / {duel.opponent_hp} HP<progress aria-label={`Your slot ${match.opponent_position + 1} HP`} value={ohp} max={duel.opponent_hp} /></label>
            <label>Counter · {chp} / {duel.counter_hp} HP<progress aria-label={`Counter slot ${match.opponent_position + 1} HP`} value={chp} max={duel.counter_hp} /></label>
          </div>
          <p>{done ? { counter: "Counter wins", opponent: "Your Pokémon wins", draw: "Both knocked out", stalemate: "Stalemate" }[duel.result] : "In progress"} · {duel.order === "simultaneous" ? "Equal Speed: simultaneous attacks" : `${duel.order === "counter" ? "Counter" : "Your Pokémon"} attacks first`}</p>
          <details><summary>Damage calculation and turn log</summary>
            <Formula strike={duel.outgoing} label="Counter attack" />
            <Formula strike={duel.incoming} label="Your attack" />
            <p>Damage is the nominal per-hit value, before clamping HP to zero. A knocked-out Pokémon cannot retaliate, except on simultaneous turns. A zero damage entry can mean an immunity or an attack prevented by knockout.</p>
            <ol>{duel.turns.slice(0, turn).map(step => <li key={step.turn}>
              Turn {step.turn}: counter dealt {step.counter_damage}, your Pokémon dealt {step.opponent_damage}. Remaining HP: counter {step.counter_hp}, yours {step.opponent_hp}.
            </li>)}</ol>
            <small>Model: {duel.model_version} · Every duel starts at full HP.</small>
          </details>
        </li>;
      })}</ol>
    </>}
  </section>;
}
