import itertools
import random
from datetime import datetime, timezone

import pytest
from app import counters
from app.counters import PairScore, effectiveness, generate_counter, score_matchup
from app.team_schemas import PokemonRead


def pokemon(identifier, types=("normal",), **stats):
    values = dict(hp=50, attack=50, defense=50, special_attack=50, special_defense=50, speed=50)
    values.update(stats)
    return PokemonRead(id=identifier, name=f"pokemon-{identifier}", types=list(types), stats=values,
                       sprite_url=None, synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def ids(preview):
    return tuple(match.counter.id for match in preview.matchups)


def objective(preview):
    return preview.safe_count, int(preview.type_strength * 4), preview.stats_score


@pytest.mark.parametrize("attack,defense,expected", [
    ("water", ["rock", "ground"], 4),
    ("electric", ["water", "ground"], 0),
    ("fire", ["water", "rock"], 0.25),
    ("normal", ["ghost"], 0),
    ("fairy", ["dragon"], 2),
    ("ghost", ["steel"], 1),
])
def test_modern_chart_dual_types_resistances_and_immunity(attack, defense, expected):
    assert effectiveness(attack, defense) == expected


def test_choose_one_best_own_attack_type_and_check_return_attack():
    pair = score_matchup(pokemon(1, ("water", "grass")), pokemon(2, ("rock", "ground")))
    assert pair.outgoing == 4  # Not 16: one move has only one type.
    assert pair.attacking_type == "grass"  # Equal effectiveness: deterministic name tie.
    assert pair.incoming_type == "rock"
    assert pair.incoming == 1
    assert pair.safe
    risky = score_matchup(pokemon(3, ("water",)), pokemon(4, ("fire", "grass")))
    assert risky.incoming_type == "grass"
    assert risky.incoming == 2
    assert not risky.safe


def test_exact_optimizer_avoids_greedy_trap_and_prioritizes_safe_count(monkeypatch):
    # Candidate 1 is versatile; candidate 2 can safely handle only opponent 10.
    # Greedily using candidate 1 on slot 0 would lose one safe matchup.
    def pair(candidate, opponent):
        safe = candidate.id == 1 or (candidate.id == 2 and opponent.id == 10)
        outgoing = 2 if safe else 4
        incoming = 1 if safe else 2
        return PairScore("normal", "normal", outgoing, incoming, safe, 1000, 1000, 1000)
    monkeypatch.setattr(counters, "score_matchup", pair)
    result = generate_counter([pokemon(10), pokemon(11)], [pokemon(1), pokemon(2)])
    assert result.safe_count == 2
    assert ids(result) == (2, 1)


def test_type_strength_precedes_stats_and_stats_precede_id(monkeypatch):
    def pair(candidate, opponent):
        # All safe, but candidate 3 has stronger typing despite very low stats.
        return PairScore("water", "fire", 4 if candidate.id == 3 else 2, 0.5,
                         True, 0 if candidate.id == 3 else candidate.id * 100,
                         0, 0)
    monkeypatch.setattr(counters, "score_matchup", pair)
    assert ids(generate_counter([pokemon(10)], [pokemon(1), pokemon(2), pokemon(3)])) == (3,)
    assert ids(generate_counter([pokemon(10)], [pokemon(1), pokemon(2)])) == (2,)


def test_deterministic_lowest_ordered_ids_and_distinct_candidates():
    targets = [pokemon(10)] * 3
    candidates = [pokemon(3), pokemon(1), pokemon(2), pokemon(4)]
    result = generate_counter(targets, candidates)
    assert ids(result) == (1, 2, 3)
    assert ids(generate_counter(targets, list(reversed(candidates)))) == ids(result)
    assert len(set(ids(result))) == 3
    assert [match.opponent_position for match in result.matchups] == [0, 1, 2]
    assert result.safe_count == 0


def test_stats_use_relative_physical_special_bulk_and_speed():
    strong = pokemon(1, attack=100, defense=100, special_attack=100, special_defense=100, hp=100, speed=100)
    weak = pokemon(2)
    pair = score_matchup(strong, weak)
    assert pair.attack_potential == 667
    assert pair.durability == 800
    assert pair.speed == 667
    assert pair.stats == 2134
    zeros = pokemon(3, hp=0, attack=0, defense=0, special_attack=0, special_defense=0, speed=0)
    assert score_matchup(zeros, zeros).stats == 1500


def test_exact_result_matches_independent_exhaustive_assignment():
    rng = random.Random(42)
    kinds = [("water",), ("grass", "poison"), ("fire",), ("electric",), ("ground", "rock")]
    for _ in range(6):
        candidates = [pokemon(i + 1, kind, **{stat: rng.randint(1, 180) for stat in
                      ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]})
                      for i, kind in enumerate(kinds)]
        opponents = [pokemon(i + 20, kinds[rng.randrange(len(kinds))]) for i in range(3)]
        possibilities = []
        for assignment in itertools.permutations(candidates, len(opponents)):
            scores = [score_matchup(candidate, target).objective for candidate, target in zip(assignment, opponents)]
            total = tuple(sum(score[index] for score in scores) for index in range(3))
            possibilities.append((total, tuple(candidate.id for candidate in assignment)))
        best_score = max(total for total, _ in possibilities)
        best_ids = min(lineup for total, lineup in possibilities if total == best_score)
        result = generate_counter(opponents, candidates)
        assert objective(result) == best_score
        assert ids(result) == best_ids
        for match in result.matchups:
            assert match.safe == (match.outgoing_multiplier >= 2 and match.incoming_multiplier <= 1)


@pytest.mark.parametrize("targets,candidates", [([], [pokemon(1)]), ([pokemon(1)] * 7, [pokemon(1)]), ([pokemon(1)] * 2, [pokemon(1)])])
def test_invalid_generation_sizes_rejected(targets, candidates):
    with pytest.raises(ValueError):
        generate_counter(targets, candidates)
