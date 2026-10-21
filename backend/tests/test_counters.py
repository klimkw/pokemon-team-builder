import itertools
import random
from datetime import datetime, timezone

import pytest
from app.services import counters
from app.services.counters import PairScore, effectiveness, generate_counter, score_matchup
from app.schemas.teams import PokemonRead


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


def test_reusable_candidates_prioritize_safe_count(monkeypatch):
    # Candidate 1 may cover both slots; lower-ID ties remain deterministic.
    def pair(candidate, opponent):
        safe = candidate.id == 1 or (candidate.id == 2 and opponent.id == 10)
        outgoing = 2 if safe else 4
        incoming = 1 if safe else 2
        return PairScore("normal", "normal", outgoing, incoming, safe, 1000, 1000, 1000)
    monkeypatch.setattr(counters, "score_matchup", pair)
    result = generate_counter([pokemon(10), pokemon(11)], [pokemon(1), pokemon(2)])
    assert result.safe_count == 2
    assert ids(result) == (1, 1)


def test_type_strength_precedes_stats_and_stats_precede_id(monkeypatch):
    def pair(candidate, opponent):
        # All safe, but candidate 3 has stronger typing despite very low stats.
        return PairScore("water", "fire", 4 if candidate.id == 3 else 2, 0.5,
                         True, 0 if candidate.id == 3 else candidate.id * 100,
                         0, 0)
    monkeypatch.setattr(counters, "score_matchup", pair)
    assert ids(generate_counter([pokemon(10)], [pokemon(1), pokemon(2), pokemon(3)])) == (3,)
    assert ids(generate_counter([pokemon(10)], [pokemon(1), pokemon(2)])) == (2,)


def test_deterministic_lowest_ids_with_duplicate_counters():
    targets = [pokemon(10)] * 3
    candidates = [pokemon(3), pokemon(1), pokemon(2), pokemon(4)]
    result = generate_counter(targets, candidates)
    assert ids(result) == (1, 1, 1)
    assert ids(generate_counter(targets, list(reversed(candidates)))) == ids(result)
    assert len(set(ids(result))) == 1
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
        for assignment in itertools.product(candidates, repeat=len(opponents)):
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


@pytest.mark.parametrize("targets,candidates", [([], [pokemon(1)]), ([pokemon(1)] * 7, [pokemon(1)]), ([pokemon(1)], [])])
def test_invalid_generation_sizes_rejected(targets, candidates):
    with pytest.raises(ValueError):
        generate_counter(targets, candidates)


def test_six_identical_venusaurs_reuse_best_counter_even_with_small_catalog():
    venusaur = pokemon(3, ('grass', 'poison'))
    candidates = [pokemon(4, ('fire',)), pokemon(7, ('water',)), pokemon(25, ('electric',))]
    single = generate_counter([venusaur], candidates)
    result = generate_counter([venusaur] * 6, candidates)
    assert ids(result) == ids(single) * 6
    assert result.stats_score == single.stats_score * 6
    assert result.safe_count == single.safe_count * 6
    assert all(match.simulation == result.matchups[0].simulation for match in result.matchups)


def test_ratio_rounding_matches_exact_rational_arithmetic_and_invariants():
    from fractions import Fraction
    from app.services.counters import ratio_score
    for a in range(40):
        for b in range(40):
            exact = Fraction(1000 * a, a + b) if a + b else Fraction(500)
            expected = (2 * exact.numerator + exact.denominator) // (2 * exact.denominator)
            assert ratio_score(a, b) == expected
            assert 0 <= ratio_score(a, b) <= 1000
            assert ratio_score(a + 1, b) >= ratio_score(a, b)
    assert ratio_score(1, 15) == 63  # Exactly 62.5 rounds up.


def test_repeat_and_permutation_preserve_independent_slot_results():
    candidates = [pokemon(1, ('fire',)), pokemon(2, ('water',)), pokemon(3, ('grass',))]
    targets = [pokemon(10, ('grass',)), pokemon(11, ('fire',)), pokemon(12, ('water',))]
    result = generate_counter(targets, candidates)
    permuted = generate_counter(list(reversed(targets)), list(reversed(candidates)))
    assert ids(permuted) == tuple(reversed(ids(result)))
    assert objective(permuted) == objective(result)
    for match in result.matchups:
        alone = generate_counter([match.opponent], candidates)
        assert match.counter.id == alone.matchups[0].counter.id
