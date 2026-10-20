"""Exact distinct-candidate assignment, with lexicographic priorities.

Maximize (safe matchup count, total type strength, total stats tie-break).
Only after all three tie, choose the lexicographically lowest ordered ID list.
The bitmask DP processes each candidate once: O(catalog_size * n * 2**n), n <= 6.
"""
from dataclasses import dataclass
from functools import lru_cache, partial
import hashlib
import json
from pathlib import Path
from typing import get_args
from app.schemas.counters import CounterMatchup, CounterPreview
from app.schemas.teams import PokemonRead, PokemonType

MODEL_VERSION = "safe-coverage-v1"


@lru_cache(maxsize=1)
def type_chart():
    data = json.loads((Path(__file__).parents[1] / "data" / "type_chart.json").read_text())
    rows = data["damage_to"]
    types = set(get_args(PokemonType))
    if set(rows) != types or any(set(row) != types for row in rows.values()):
        raise ValueError("Type chart must contain all 18 attack and defense types")
    if any(value not in (0, 0.5, 1, 2) for row in rows.values() for value in row.values()):
        raise ValueError("Unexpected type multiplier")
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    if data["version"] != "sha256:" + hashlib.sha256(canonical.encode()).hexdigest():
        raise ValueError("Type chart content does not match its version")
    return data


def effectiveness(attacking_type: str, defending_types: list[str], chart=None) -> float:
    row = (chart or type_chart())["damage_to"][attacking_type]
    result = 1.0
    for defending_type in defending_types:
        result *= row[defending_type]
    return result


def best_attack(attacker: PokemonRead, defender: PokemonRead, chart=None) -> tuple[str, float]:
    # Attack with ONE own type, never multiply the attacker's two types together.
    # Alphabetical ordering makes tied attack-type explanations deterministic.
    return max(((kind, effectiveness(kind, defender.types, chart)) for kind in sorted(attacker.types)),
               key=lambda item: item[1])


def ratio_score(a: int, b: int) -> int:
    """Relative advantage in [0, 1000], integer-rounded; zero vs zero is neutral."""
    total = a + b
    return (1000 * a + total // 2) // total if total else 500


@dataclass(frozen=True)
class PairScore:
    attacking_type: str
    incoming_type: str
    outgoing: float
    incoming: float
    safe: bool
    attack_potential: int
    durability: int
    speed: int

    @property
    def stats(self):
        return self.attack_potential + self.durability + self.speed

    @property
    def objective(self):
        # Type multipliers are exact multiples of 1/4. Integers avoid float ties.
        return (int(self.safe), int(4 * (self.outgoing - self.incoming)), self.stats)


def score_matchup(candidate: PokemonRead, opponent: PokemonRead, chart=None) -> PairScore:
    attacking_type, outgoing = best_attack(candidate, opponent, chart)
    incoming_type, incoming = best_attack(opponent, candidate, chart)
    c, o = candidate.stats, opponent.stats
    attack = max(ratio_score(c.attack, o.defense), ratio_score(c.special_attack, o.special_defense))
    durability = (ratio_score(c.hp * c.defense, o.hp * o.attack)
                  + ratio_score(c.hp * c.special_defense, o.hp * o.special_attack)) // 2
    speed = ratio_score(c.speed, o.speed)
    return PairScore(attacking_type, incoming_type, outgoing, incoming,
                     outgoing >= 2 and incoming <= 1, attack, durability, speed)


def generate_counter(opponents: list[PokemonRead], candidates: list[PokemonRead], chart=None) -> CounterPreview:
    if not 1 <= len(opponents) <= 6:
        raise ValueError("Counter generation requires 1–6 opponents")
    by_id = {candidate.id: candidate for candidate in candidates}
    if len(by_id) < len(opponents):
        raise ValueError("Not enough distinct catalog entries")
    scorer = score_matchup if chart is None else partial(score_matchup, chart=chart)
    size = len(opponents)
    # mask -> (objective, IDs by opposing slot). Zero is an unassigned slot.
    states = {0: ((0, 0, 0), (0,) * size)}
    for candidate in sorted(by_id.values(), key=lambda pokemon: pokemon.id):
        pairs = [scorer(candidate, opponent).objective for opponent in opponents]
        previous = states
        states = previous.copy()  # Skipping this candidate is always permitted.
        for mask, (objective, ids) in previous.items():
            for index, contribution in enumerate(pairs):
                bit = 1 << index
                if mask & bit:
                    continue
                next_mask = mask | bit
                score = tuple(a + b for a, b in zip(objective, contribution))
                lineup = ids[:index] + (candidate.id,) + ids[index + 1:]
                incumbent = states.get(next_mask)
                if incumbent is None or score > incumbent[0] or (score == incumbent[0] and lineup < incumbent[1]):
                    states[next_mask] = (score, lineup)
    objective, ids = states[(1 << size) - 1]
    matches = []
    for index, (opponent, candidate_id) in enumerate(zip(opponents, ids)):
        candidate = by_id[candidate_id]
        pair = scorer(candidate, opponent)
        matches.append(CounterMatchup(opponent_position=index, opponent=opponent, counter=candidate,
            attacking_type=pair.attacking_type, incoming_type=pair.incoming_type,
            outgoing_multiplier=pair.outgoing, incoming_multiplier=pair.incoming,
            safe=pair.safe, type_strength=pair.outgoing - pair.incoming,
            attack_potential=pair.attack_potential, durability=pair.durability, speed=pair.speed,
            stats_score=pair.stats))
    return CounterPreview(model_version=MODEL_VERSION, chart_version=(chart or type_chart())["version"],
        safe_count=objective[0], size=size, type_strength=objective[1] / 4,
        stats_score=objective[2], matchups=matches)
