# Recent-change alerts and deterministic demonstration

The assignment asks for an alert describing recent changes to a user's Pokémon and
proof that detection works. Live upstream changes are rare, so the demonstration
uses predictable local source responses while retaining the real scanner and storage.

## How alerts work

GET `/api/alerts?limit=20&offset=0` requires the normal signed-in session. It returns
only changes relevant to the current user's **saved** team membership. Unsaved edits
do not change this query; a successful save or deletion refreshes the frontend panel.
A newly added Pokémon can expose an earlier change that is still within the window.
Removing its last saved membership removes its alerts without deleting history.

`CHANGE_ALERT_WINDOW_DAYS` defaults to seven. The query includes the exact lower
boundary and excludes future timestamps. It uses observation time, not a claimed
upstream effective date. Changing the setting requires restarting the API; scanner
frequency remains independently controlled by `CATALOG_SCAN_INTERVAL_HOURS`.

A Pokémon change matches its stable ID. A type-chart row represents one attacking
type and multipliers against defensive types. A row change affects a saved Pokémon
when it has that attacking type, or when a changed defensive column is one of its
types. For defensive-only matches, irrelevant changed columns are omitted. This
follows the same types-only assumption as the counter generator, without claiming
that a particular move or battle outcome is known.

One history event appears once, with affected Pokémon and owned teams grouped below
it. Duplicate slots are listed together; API positions are zero-based and the UI
shows slots starting at one. Team names and Pokémon names use current saved state;
the event's entity name and before/after values retain the observed change.

Alerts are read-only views, not persisted notifications: no unread flag, dismissal,
email, or acknowledgement is implied. History is retained after the window expires.
The response includes the most recent scan's status/time so an empty list cannot be
mistaken for proof that every source was checked. It exposes no raw scanner errors.
Authenticated responses use `Cache-Control: no-store`.

The initial implementation loads the user's saved memberships and recent candidate
history, filters relevance, then paginates. This keeps JSON matching portable across
SQLite and PostgreSQL and ensures totals count relevant events. At substantially
larger history volumes, move relevance/counting into indexed PostgreSQL queries.
Offset pagination is intended for this small feed; newly arriving changes can shift
pages, and Refresh returns to the latest entries.

## Local demonstration, separate from development

`compose.demo.yaml` is a standalone stack named `pokemon-team-builder-demo`. Never
combine it with compose.yaml or compose.test.yaml. It has a separate network and a
PostgreSQL database named `pokemon_demo`, held in temporary memory-backed storage.
It does not mount the development volume or consume its database password. No normal
scanner service runs in the demo; each stage explicitly runs the offline scenario.

From the repository root:

```powershell
docker compose -p pokemon-team-builder-demo -f compose.demo.yaml up --build -d --wait demo-api demo-frontend
docker compose -p pokemon-team-builder-demo -f compose.demo.yaml run --rm demo-run python -m app.jobs.demo baseline
```

Open http://localhost:8081 and sign in with username `demo_trainer` and password
`Demo-only-password-2026`. These are public fixture credentials for this disposable
local stack. The initial saved team has Bulbasaur twice and Charmander once. The
alert panel should show zero changes. Then run:

```powershell
docker compose -p pokemon-team-builder-demo -f compose.demo.yaml run --rm demo-run python -m app.jobs.demo change
```

Choose **Refresh alerts** in the browser. It shows:

- Bulbasaur's Attack changed from 49 to 60, affecting saved slots 1 and 2.
- Fire attacks against Grass changed from 2× to 1×. Bulbasaur is affected defensively;
  Charmander is affected because Fire is its attacking type in our model.

The type change is deliberately fictional and marked as a demonstration, not a real
PokéAPI update. Pokémon payloads live in `app/data/demo_pokemon.json`; the type baseline
comes from the bundled chart. `httpx.MockTransport` supplies all source responses and
rejects requests outside the fixtures. The real PokéAPI client still discovers and
validates them, and the normal scanner writes the catalog/history atomically under
its PostgreSQL advisory lock. Alerts are fetched through the ordinary authenticated API.

Repeat the changed inputs:

```powershell
docker compose -p pokemon-team-builder-demo -f compose.demo.yaml run --rm demo-run python -m app.jobs.demo repeat
```

The output reports three unchanged Pokémon, 18 unchanged type rows, and exactly two
history entries before and after the scan. Refreshing the UI still shows two alerts.
Each stage asserts its expected history and alert counts and exits nonzero on failure.
The default `demo-run` command runs all three stages consecutively for automated proof:

```powershell
docker compose -p pokemon-team-builder-demo -f compose.demo.yaml run --rm demo-run
```

Use that default only with a fresh demo stack. Baseline refuses a database that already
contains change history rather than silently undoing the demonstration. To start over,
stop this **demo** project, then start it and run baseline again:

```powershell
docker compose -p pokemon-team-builder-demo -f compose.demo.yaml down
```

Stopping/removing its database container discards this temporary demo data. Do not run
cleanup commands against the development project. The CLI requires `DEMO_MODE=true`
and the PostgreSQL database name `pokemon_demo`, rejecting development/test URLs.
The two local frontends use distinct cookie names, so signing into the demo does not
replace your development login. Demo API docs are at http://localhost:8001/docs.

After a scan, Refresh alerts updates the feed without replacing any editor draft.
Reload the page when you want updated catalog/member stats in the editor; protect or
save unsaved changes first. Detection time and generated UUIDs vary per run; fixture
changes, affected slots, event counts and repeat behavior are deterministic.

## Verification and eventual public demo

Backend tests exercise ownership, duplicate memberships, time boundaries, custom
window length, type relevance, live saved membership, pagination, and scan freshness.
An isolated PostgreSQL test runs baseline/change/repeat with real scanner code and
logs into the fixture account to read its alerts. Component tests cover differences,
empty/error/retry states, type direction, pagination and request cancellation. Chromium
checks real alerts, duplicate slots, unsaved versus saved membership, and mobile width.

The local Docker demonstration is implemented. A hosted browser-controlled walkthrough
is a later deployment adaptation: each visitor should get an isolated temporary
scenario, with bounded creation/cleanup. It can reuse the deployed API and database
server, and invoke this small fixture scan on demand. It must not rewrite live catalog
rows or let visitors reset someone else's scenario. Hosting, public demo controls,
session isolation/expiry, and deployment-specific scheduling are not implemented here.
