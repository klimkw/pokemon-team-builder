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
