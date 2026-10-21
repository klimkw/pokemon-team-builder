"""Deterministic illustrative paired duels; not a competitive battle engine."""
from app.schemas.counters import Duel, DuelTurn, Strike

MAX_TURNS = 200


def strike(attacker, defender, multiplier, attack_type):
    a, d = attacker.stats, defender.stats
    category = ('physical' if a.attack * max(1, d.special_defense) >= a.special_attack * max(1, d.defense) else 'special')
    attack = a.attack if category == 'physical' else a.special_attack
    defense = max(1, d.defense if category == 'physical' else d.special_defense)
    # Fictional equal-power own-type attacks. Immunities bypass the minimum damage.
    damage = 0 if multiplier == 0 else max(1, (30 * attack * int(multiplier * 4)) // (4 * defense))
    return Strike(category=category, attack_type=attack_type, attack=attack, defense=defense,
                  effectiveness=multiplier, damage=damage)


def simulate_duel(match):
    counter, opponent = match.counter, match.opponent
    chp, ohp = max(1, counter.stats.hp), max(1, opponent.stats.hp)
    outgoing = strike(counter, opponent, match.outgoing_multiplier, match.attacking_type)
    incoming = strike(opponent, counter, match.incoming_multiplier, match.incoming_type)
    order = ('simultaneous' if counter.stats.speed == opponent.stats.speed else
             'counter' if counter.stats.speed > opponent.stats.speed else 'opponent')
    turns = []
    for number in range(1, MAX_TURNS + 1):
        cd, od = 0, 0
        if order == 'simultaneous':
            cd, od = outgoing.damage, incoming.damage
            chp, ohp = max(0, chp - od), max(0, ohp - cd)
        elif order == 'counter':
            cd = outgoing.damage
            ohp = max(0, ohp - cd)
            if ohp:
                od = incoming.damage
                chp = max(0, chp - od)
        else:
            od = incoming.damage
            chp = max(0, chp - od)
            if chp:
                cd = outgoing.damage
                ohp = max(0, ohp - cd)
        turns.append(DuelTurn(turn=number, counter_hp=chp, opponent_hp=ohp,
                              counter_damage=cd, opponent_damage=od))
        if not chp or not ohp or (outgoing.damage == incoming.damage == 0):
            break
    result = 'draw' if chp == ohp == 0 else 'counter' if ohp == 0 else 'opponent' if chp == 0 else 'stalemate'
    return Duel(result=result, order=order,
                counter_hp=max(1, counter.stats.hp), opponent_hp=max(1, opponent.stats.hp),
                outgoing=outgoing, incoming=incoming, turns=turns)
