from types import SimpleNamespace
from app.schemas.teams import PokemonRead
from app.services.battle import simulate_duel, strike


def pokemon(identifier=1, **stats):
    values = dict(hp=100, attack=50, defense=50, special_attack=50, special_defense=50, speed=50)
    values.update(stats)
    return PokemonRead(id=identifier, name='test', types=['normal'], stats=values,
                       sprite_url=None, synced_at='2026-10-20T12:00:00Z')


def duel(c, o, outgoing=1, incoming=1):
    return simulate_duel(SimpleNamespace(counter=c, opponent=o, outgoing_multiplier=outgoing,
        incoming_multiplier=incoming, attacking_type='normal', incoming_type='normal'))


def test_damage_formula_category_and_immunity():
    result = strike(pokemon(attack=60), pokemon(defense=50), 2, 'normal')
    assert result.category == 'physical' and result.damage == 72
    result = strike(pokemon(special_attack=100), pokemon(), .5, 'normal')
    assert result.category == 'special' and result.damage == 30
    assert strike(pokemon(), pokemon(), 0, 'normal').damage == 0
    assert strike(pokemon(attack=0, special_attack=0), pokemon(defense=0, special_defense=0), 1, 'normal').damage == 1


def test_speed_prevents_retaliation_and_reports_nominal_damage():
    c, o = pokemon(speed=60, attack=100), pokemon(2, hp=10)
    result = duel(c, o)
    assert result.result == 'counter' and result.order == 'counter'
    assert len(result.turns) == 1
    assert result.turns[0].counter_damage == 60 and result.turns[0].opponent_damage == 0
    assert result.turns[0].opponent_hp == 0 and result.turns[0].counter_hp == 100
    reverse = duel(o, c)
    assert reverse.result == 'opponent' and reverse.order == 'opponent'
    assert reverse.turns[0].counter_damage == 0


def test_equal_speed_simultaneous_draw_and_reproducible():
    c, o = pokemon(hp=10), pokemon(2, hp=10)
    result = duel(c, o)
    assert result.order == 'simultaneous' and result.result == 'draw'
    assert result.turns[0].counter_damage == result.turns[0].opponent_damage == 30
    assert result.model_dump() == duel(c, o).model_dump()


def test_stalemates_zero_hp_and_turn_cap():
    assert duel(pokemon(), pokemon(2), 0, 0).result == 'stalemate'
    assert len(duel(pokemon(), pokemon(2), 0, 0).turns) == 1
    result = duel(pokemon(hp=999, attack=0, special_attack=0), pokemon(2, hp=999, attack=0, special_attack=0))
    assert result.result == 'stalemate' and len(result.turns) == 200
    result = duel(pokemon(hp=0), pokemon(2, hp=0))
    assert result.counter_hp == result.opponent_hp == 1
    assert result.result == 'draw'


def test_safe_types_do_not_guarantee_duel_win():
    result = duel(pokemon(hp=10, speed=1), pokemon(2, speed=100), 2, 1)
    assert result.result == 'opponent'


def test_turn_log_conserves_hp_and_matches_announced_strikes():
    for speed in [1, 50, 100]:
        result = duel(pokemon(hp=120, speed=speed), pokemon(2, hp=100), .5, 1)
        chp, ohp = result.counter_hp, result.opponent_hp
        for step in result.turns:
            assert step.counter_damage in (0, result.outgoing.damage)
            assert step.opponent_damage in (0, result.incoming.damage)
            assert step.counter_hp == max(0, chp - step.opponent_damage)
            assert step.opponent_hp == max(0, ohp - step.counter_damage)
            assert 0 <= step.counter_hp <= chp and 0 <= step.opponent_hp <= ohp
            chp, ohp = step.counter_hp, step.opponent_hp
        assert result.result == ('counter' if ohp == 0 and chp else 'opponent' if chp == 0 and ohp else 'draw')


def test_damage_rounding_matches_exact_fractions_at_boundaries():
    from fractions import Fraction
    for attack, defense in [(0, 0), (1, 3), (7, 9), (60, 50), (999, 1)]:
        for multiplier in [0, .25, .5, 1, 2, 4]:
            result = strike(pokemon(attack=attack, special_attack=0), pokemon(defense=defense), multiplier, 'normal')
            exact = Fraction(30 * attack, max(1, defense)) * Fraction(multiplier)
            expected = 0 if multiplier == 0 else max(1, exact.numerator // exact.denominator)
            assert result.damage == expected
