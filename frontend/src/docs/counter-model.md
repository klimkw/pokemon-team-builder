# Counter teams: scoring and simulation

This is the single source for the guide at /counter-method. Edit this Markdown file in the repository to update the web page. The page is built into the frontend, works without an external documentation service and can be downloaded as Markdown.

## What “optimal” means here

Optimal means the best lineup under the explicit type-and-base-stat objective below. It does not mean the best competitive Pokémon team. Selection and the illustrative duel simulation are separate models. A type-safe pairing can lose a simulated duel because of Speed, HP or attacking/defensive stats. The simulation does not select or rerank the counters.

The generator uses the editor's current ordered Pokémon IDs, including unsaved changes. There are one to six opposing slots. The counter has one distinct catalog ID per slot. Opponents may repeat; counter IDs may not. All catalog entries, including alternate forms and legendary Pokémon, are eligible, and an opponent's own ID is not excluded. Distinct forms of the same species count as different catalog IDs. There is no budget, generation or competitive legality filter.

## 1. Compute each pair's type matchup

For one attacking type, multiply its chart entry against every defending type. For example, a 2× advantage against one defending type and 0.5× against the other yields 1×. An immunity makes the entire result zero.

The attacker chooses the best ONE of its own types. Do not multiply its two attacking types together. Equal effectiveness chooses the alphabetically first attacking type, giving reproducible explanations. Both sides make this choice independently, so the preview shows outgoing and incoming effectiveness.

```text
outgoing = max(effectiveness(t, opponent.types) for t in counter.types)
incoming = max(effectiveness(t, counter.types) for t in opponent.types)
safe = outgoing >= 2 AND incoming <= 1
type_strength = outgoing - incoming
```

These are assumed own-type attacks; the catalog does not provide a selected moveset. A 4× multiplier is type effectiveness, not four times a known damage value or a win probability.

## 2. Rank complete lineups in strict priority order

- First: maximize the number of safe paired matchups.
- Second: among equally safe lineups, maximize the sum of outgoing minus incoming effectiveness.
- Third: among ties on both earlier priorities, maximize the sum of the base-stat scores below.
- Last: choose the lexicographically smallest counter ID list in opposing-slot order.

This is lexicographic optimization, not an adjustable weighted sum. No amount of stats can compensate for losing one safe pairing. Outgoing/incoming multipliers are multiples of one quarter for valid dual typings; type strength is multiplied by four internally to keep comparisons exact integers.

A bitmask dynamic program processes catalog candidates once. A mask records the opposing slots already filled. For each candidate, it either skips that Pokémon or places it in one unfilled slot using the previous iteration's states. This guarantees distinct IDs and considers complete assignments globally, rather than independently choosing the best counter for every slot. Runtime is O(catalog size × n × 2^n), with n at most six.

## 3. Calculate the stats tie-break

The helper R(a,b) compares two nonnegative quantities on a 0–1,000 scale, using integer arithmetic and round-half-up. R(0,0) is neutral at 500.

```text
R(a,b) = floor((1000*a + floor((a+b)/2)) / (a+b))
attack_potential = max(R(counter.Attack, opponent.Defense),
                       R(counter.SpAtk, opponent.SpDef))
durability = floor((R(counter.HP*counter.Defense, opponent.HP*opponent.Attack)
                  + R(counter.HP*counter.SpDef, opponent.HP*opponent.SpAtk)) / 2)
speed = R(counter.Speed, opponent.Speed)
stats_score = attack_potential + durability + speed
```

Each pair has a score from 0 to 3,000. Team stats score is the sum. These are relative ranking components, not percentages or predicted damage. The preview exposes the components, team totals, selected types and raw base stats so you can audit the result.

## Matchup simulation: a deliberately simplified model

Choose Run matchup simulation to start each displayed pair at full HP. Next turn advances all independent duels by one turn. Show result jumps to the final states; Restart returns to full HP. Each pair's damage calculation and turn log can be expanded. Summary wins count paired duels, not a team-battle win probability. No random trials or probabilities are involved.

We use a custom, equal-power base-stat damage model for illustration. This is NOT the official Pokémon damage formula. Base HP is the starting HP pool, not a level-adjusted battle stat. The model intentionally uses only data already available in the catalog and active type chart.

- Each side always uses its best own-type effectiveness from the displayed matchup.
- It independently chooses physical or special attacks by the higher Attack/Defense ratio; equal ratios choose physical. Category is not restricted by a learned move.
- HP is max(1, base HP). Defense and Special Defense denominators are clamped to at least 1 to handle manual zero-stat scenarios safely.
- The equal-power damage constant is 20 and the assumed own-type bonus is 1.5. Nonimmune damage is rounded down, with a minimum of 1. Immunity always deals 0.

```text
physical_ratio = base Attack / max(1, opposing base Defense)
special_ratio = base SpAtk / max(1, opposing base SpDef)
choose the category with the larger ratio (physical on ties)
damage = 0 if effectiveness == 0
otherwise damage = max(1, floor(20 * chosen_ratio * 1.5 * effectiveness))
remaining_HP = max(0, remaining_HP - damage)
```

For example, with chosen Attack 60, opposing Defense 50 and effectiveness 2×, nominal damage is floor(20 × 60/50 × 1.5 × 2) = 72. A defender with 45 remaining HP drops to zero. The log reports the nominal 72 damage; actual HP lost is capped at the remaining 45. If the defender is faster it may attack before this hit, changing the outcome.

## Turn order, knockouts and stopping

Higher base Speed attacks first every turn. If that attack knocks out the other Pokémon, the knocked-out side does not retaliate. Equal Speed produces simultaneous attacks: both hits occur, and a double knockout is a draw. This tie rule avoids giving either side an arbitrary first-turn advantage.

Every paired duel starts independently at full HP. HP is not carried between slots. There is no switching, targeting another slot, team sweep, healing, PP, status, weather, critical hits, accuracy, damage randomness, ability, item, level, nature, IV, EV or learned-move simulation. This is a coverage illustration, not a battle simulator such as Pokémon Showdown.

A duel ends on a knockout. Mutual immunities stop after the first zero-damage turn. A safety limit of 200 turns prevents unusually slow manual scenarios from running indefinitely. If both still have HP at the limit (or cannot damage each other), the result is a stalemate, not an inferred winner. The replay reports counter wins, your wins, simultaneous knockout draws and stalemates separately.

## Reproducibility and live data

The preview reports selection model safe-coverage-v1 and the active type-chart hash. Every duel reports paired-base-stats-v1. The replay uses the exact Pokémon and type multipliers from that preview, without fetching new catalog values mid-replay. Identical inputs and versions produce identical outputs. A later live refresh or manual change can alter newly generated results; an open preview stays a snapshot. Generate a new preview to use newer data.

Generation, simulation and replay do not save teams, edit the source lineup, mutate the catalog or generate alerts. Save as new team is the explicit persistence action. Saved counter teams store Pokémon membership, not a frozen battle report; reopening them uses current catalog data.

## Implementation and verification

Selection is implemented in backend/app/services/counters.py; illustrative duels in backend/app/services/battle.py. The API is POST /api/teams/counter-preview. Shared cards live in frontend/src/PokemonDetails.tsx, the comparison in CounterPreview.tsx and the replay in BattleReplay.tsx. This guide is frontend/src/docs/counter-model.md.

Selection tests compare the exact solver with brute-force assignments on small catalogs and check priority ordering, duplicate opponents, distinct candidates, type immunities, dual types and deterministic ties. Duel tests cover physical/special choice, damage arithmetic, immunities, speed order, prevented retaliation, simultaneous knockouts, zero-stat handling, the turn cap and deterministic output. Browser tests exercise shared cards, replay controls, the guide, mobile width and explicit saving without changing the original draft.
