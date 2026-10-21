# Counter comparison, replay and model guide

The owner identified explainable counter generation as the central take-home feature
and requested shared Pokédex cards, opposing matchups side by side, battle simulation
and a repo-managed Markdown explanation linked from the web app.

The existing selection objective stays unchanged: exact distinct-ID assignment,
lexicographically maximizing safe coverage, type strength and stat score, then lowest
ordered IDs. The catalog and preview now use the same PokemonCard, Sprite, TypeBadges
and StatList components. Each pairing shows your Pokémon left and its counter right,
with six base stats, type chips, effectiveness directions and score detail.

Simulation is deliberately separate from optimization. A small pure Python service
computes independent paired duels from the same selected Pokémon and chart multipliers.
It uses a custom equal-power own-type damage model, base HP, physical/special ratio
choice, Speed order, simultaneous ties, immunity, knockout-prevented retaliation and
bounded stalemates. It does not claim official damage, real battle strategy or a win
probability. The preview response adds each duel's version, inputs and turn snapshots.
The frontend offers run, next turn, show result and restart with HP bars and exact
formula/log disclosures. Replay does not write teams or alter source data.

frontend/src/docs/counter-model.md is the single source for the rendered /counter-method
page. It documents formulas, examples, algorithm complexity, candidate scope, tie rules,
limits and versions. ModelGuide renders headings, paragraphs, lists and code as React
text without unsafe HTML or CDN dependencies. A download link provides that exact
Markdown source. README links to the same file, avoiding a second competing spec.

Tests cover mathematical damage examples, category choice, zero stats, immunity,
Speed/retaliation, simultaneous knockouts, turn caps, reproducibility and a type-safe
pair that loses. Existing brute-force optimizer comparisons still check unchanged
selection. API tests inspect the duel contract and side-effect-free repeatability.
Component/browser tests cover cards, replay controls, formulas, guide navigation,
mobile width and explicit saving while retaining the original unsaved draft.

Verification passed 134 PostgreSQL tests, 118 SQLite tests (16 PostgreSQL-only skips),
27 components and six regular Chromium flows (legacy separate demo skipped). After
adding the simulation shortcut and directional labels, frontend build/component/browser
checks reran successfully. Screenshots reviewed for both card layouts, desktop/mobile
replay with formula disclosure and the guide. Reports: test-artifacts/counter-replay/.
An initial replay test syntax error was corrected before testing. Commit this increment
as “Add shared counter cards, transparent duel replay and model guide”.
