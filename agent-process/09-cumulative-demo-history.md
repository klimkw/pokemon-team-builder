# Cumulative demo and alert timeline

The owner requested a way to build changes across API-docs requests and see repeated
changes over the configured alert window. Each request still queues one worker job;
requests cannot run concurrently. Subsequent requests reuse the active demo ID.

The stored originals snapshot now merges fields instead of rejecting different
payloads. A field keeps its first before value and latest requested after value.
New Pokémon, stats and matchup pairs can be added. Repeating a request against the
same current values creates no new change events. Reset restores all tracked fields
and removes all history tagged to that demo ID. Updates refuse to replace tracked
fields whose current value differs from the last demo value, protecting newer source
data. Existing snapshots remain compatible; no migration is required.

Alert cards are grouped by local calendar date, newest first, retaining exact detection
timestamps. A View history disclosure appears for fields with multiple changes. It
shows each before/after transition with its detection timestamp, newest first. The
API builds histories by stable entity kind/key and field, after saved-team relevance
and the configured time window are applied, before pagination. A history therefore
includes relevant entries on other pages without including unrelated Pokémon or old
changes. These are scanner detection times, not asserted upstream modification times.

Verification covers cumulative same/new fields and type pairs, idempotent repeats,
reset to the first value, refusal of newer source values, cross-page/window history,
date grouping and expandable history in the normal admin browser flow. Reports and
screenshots are retained locally under test-artifacts/alert-history/.

Results: 129 PostgreSQL, 113 SQLite (16 skips), 25 component tests and six regular
Chromium flows passed, with the old opt-in separate-demo flow skipped. Docker production
build passed after correcting a misplaced JSX closing tag in the initial draft.
The desktop screenshot shows the expanded 49 → 60 and 60 → 70 transitions, with a
single date heading for that day. Mobile width is covered in the same browser flow.
Commit: “Support cumulative demo changes and dated alert histories”.
