import { useState, type ReactNode } from "react";
import type { Pokemon } from "./api";

export const statNames: Record<keyof Pokemon["stats"], string> = {
  hp: "HP", attack: "Attack", defense: "Defense", special_attack: "Sp. Atk", special_defense: "Sp. Def", speed: "Speed",
};

export function TypeBadge({ type }: { type: string }) {
  return <span className={`type-badge type-${type}`}>{type}</span>;
}
export function TypeBadges({ types }: { types: string[] }) {
  return <div className="type-badges">{types.map(type => <TypeBadge key={type} type={type} />)}</div>;
}
export function StatList({ pokemon, className = "" }: { pokemon: Pokemon; className?: string }) {
  return <dl className={`pokemon-stats ${className}`} aria-label={`${pokemon.name} base stats`}>
    {(Object.keys(statNames) as (keyof Pokemon["stats"])[]).map(key => <div key={key}><dt>{statNames[key]}</dt><dd>{pokemon.stats[key]}</dd></div>)}
  </dl>;
}

export function Sprite({ pokemon }: { pokemon: Pokemon }) {
  const [failed, setFailed] = useState(false);
  return pokemon.sprite_url && !failed
    ? <img className="pokemon-sprite" src={pokemon.sprite_url} alt="" loading="lazy" onError={() => setFailed(true)} />
    : <span className="sprite-placeholder" aria-label="Sprite unavailable">◇</span>;
}

export function PokemonCard({ pokemon, selectedCount = 0, children }: { pokemon: Pokemon; selectedCount?: number; children?: ReactNode }) {
  return <article className={`pokemon-card ${selectedCount ? "is-selected" : ""}`} aria-label={pokemon.name}>
    <span className="pokemon-number">#{String(pokemon.id).padStart(3, "0")}</span>
    <Sprite key={pokemon.id} pokemon={pokemon} />
    <h3>{pokemon.name}</h3>
    {selectedCount > 0 && <span className="selected-label">In team · {selectedCount}</span>}
    <TypeBadges types={pokemon.types} />
    <StatList pokemon={pokemon} />
    {children}
  </article>;
}
