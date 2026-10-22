# Alerts presentation

The owner requested title-case event titles, indented affected Pokémon, shared type
chips, compact stat-change chips and typography consistent with the Pokédex.

Alerts remain in the existing header drawer. Each event is a paper card with a
Manrope heading and muted timestamp. Changed values appear in compact chips with
the old value, arrow and emphasized new value. Type multipliers use the shared
attacking and defending type badges with an accessible text description.

Affected Pokémon form an indented list with their current catalog types. Type events
also explain attacking or defensive relevance; saved team names and slot references
remain below each Pokémon. The backend adds current types to the existing affected
Pokémon response, using the same validated type contract as catalog/team responses.
No new database column or migration is required. Existing relevance, pagination,
read tracking and scanner behavior are preserved.

Verification covers affected-type metadata, title case, chip labels and markup,
defensive relevance, the existing unread/admin workflow and mobile overflow. Screenshots
are retained locally under test-artifacts/alerts-polish/ after the isolated Docker run.

Results: 127 PostgreSQL tests, 112 SQLite tests (15 skips), 24 component tests and six
regular Chromium flows passed. Production build passed. Desktop and mobile screenshot
review confirmed the card layout and consistent chips. The old separate-demo browser
flow remains opt-in and was skipped. The completed increment is committed as
“Polish alert cards and affected Pokemon type context”.
