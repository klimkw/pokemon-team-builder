# Pokemon Team Builder

Take-home project built in reviewable increments. Current increment: separately scheduled catalog scanning with atomic change history,
alongside the catalog, persistent teams, and explainable counter-team generator.

## Run and test

Copy `.env.example` to `.env` and choose a long random alphanumeric database password.
Run `docker compose up --build`, then open http://localhost:8080 for the application.
API documentation remains available at http://localhost:8000/docs (read-only browsing;
use the frontend origin for authentication requests). If you already have a `.env`
from the previous increment, change APP_ORIGIN to http://localhost:8080.
Register with JSON `{"username":"Ash","password":"long-example-password"}`.
Login uses form fields `username` and `password` (not JSON), returning 204 and a cookie.
GET `/api/auth/me` returns the user; POST `/api/auth/logout` revokes that session.
Registration does not log in automatically. Bad credentials and duplicate usernames
return the library's 400 responses; protected routes return 401 without valid access.

From `backend`, use Python 3.12 with uv: `uv sync --locked`, then
`uv run --locked python -m pytest tests -q`. Runtime/test Docker images install the committed
`uv.lock` with uv; no host Python environment is reused.
From `frontend`, use Node 22.12+ (Node 24 recommended), run `npm ci`, `npm test`, and
`npm run build`. Ninety-three backend tests pass against PostgreSQL; the fast SQLite option
skips the two PostgreSQL-only checks. All 18 frontend component tests pass. Three
Chromium E2E tests pass against PostgreSQL, FastAPI, and the production build served
through Nginx in the isolated Docker stack. TypeScript and production build pass.
See [TESTING.md](TESTING.md) for isolated Compose tests, setup, cleanup, and reports.

For development without Docker, set APP_ORIGIN=http://127.0.0.1:5173 and DATABASE_URL,
run `alembic upgrade head` from `backend`, then start `uvicorn app.main:app`.
Run `npm run dev` from `frontend`. Open the printed
http://127.0.0.1:5173 address; localhost and 127.0.0.1 are different origins.
Vite proxies `/api` to http://127.0.0.1:8000. In the Windows authoring sandbox,
esbuild dependency scanning was blocked, so browser QA used `npm run build` followed
by `npm run preview -- --port 5173`; `--configLoader native` was also supplied to Vite
and Vitest to avoid sandbox-restricted config bundling. Production Docker builds do
not require these sandbox-specific flags.

## Local development stack

The local Docker stack is running at http://localhost:8080 with the backend at
http://localhost:8000/docs. Create your own account in the UI. PostgreSQL data lives
in the persistent `pokemon-team-builder_postgres_data` volume. The ignored `.env`
contains local settings and must remain private. The frontend serves a built version;
source changes require rebuilding its image rather than appearing through hot reload.

Stop the stack with `docker compose -p pokemon-team-builder stop`; resume the current
images with `docker compose -p pokemon-team-builder up -d --no-build`. Do not remove
the database volume. In this Windows-mounted workspace, the backend host cache
metadata prevents a direct build; the current images were built from a clean
source-only copy under /tmp, without reusing host dependencies. See TESTING.md.

## Development walkthroughs

[agent-process/README.md](agent-process/README.md) indexes the detailed build journal,
PostgreSQL/Alembic walkthrough, and uv workflow. These process documents accompany
the working README; they will remain separate from the final one-page submission.

## Design decisions

- Python/FastAPI, FastAPI Users 14.0.2, async SQLAlchemy, PostgreSQL, React/TypeScript/Vite.
- React holds only the returned user in memory; it does not read or store the session
  token. On load it calls `/api/auth/me`. A 401 shows the login form; connection errors
  show a retry screen. Registration returns to sign-in with the username retained and
  password cleared. Login loads `/me`; logout revokes the session before clearing UI state.
- Nginx serves the built frontend and forwards `/api` to FastAPI in Compose. Vite supplies
  the equivalent proxy for development. Requests stay on the browser's origin, so no
  cross-origin cookie configuration or CORS middleware is required for this topology.
- The UI uses responsive CSS and Google Fonts with system-font fallbacks. Signed-in
  users see a searchable, type-filtered catalog (24 per page), with sprites and all six
  stats, beside a team editor. On smaller screens the sections stack with jump links.
- Drafts live in React memory. Save sends the name and complete ordered ID array in
  one request. Failed saves retain edits; switching teams, starting a new team, or
  signing out prompts before discarding edits. Refresh/close uses the browser warning.
  A confirmed navigation discards the draft; there is no autosave or browser storage.
- Users can create, rename, delete, select, add/remove members, and reorder with accessible
  arrow buttons. Empty teams and duplicates are allowed. Add is disabled at six members;
  mutation controls are locked during a save. A missing sprite shows a placeholder.
- FastAPI Users owns registration, password hashing, authentication, token issuance,
  expiry checks, and logout revocation. CookieTransport plus DatabaseStrategy supplies
  browser sessions. The project is in maintenance mode, including security/dependency updates.
- Username-only accounts: the library's internal `email` column stores our normalized
  username. UserCreate aliases that field to `username`; UserRead exposes `username`.
  No email is collected. Email verification, recovery, user-update and OAuth routes
  are not mounted. Revisit the model before introducing actual email functionality.
- Usernames contain 3-32 ASCII letters, digits, or underscores and are lowercased at
  registration. Library database lookup is case-insensitive. Passwords contain 8-128
  characters and use the library's Argon2 password helper. IDs are now UUIDs.
- Sessions use a random opaque token in an HttpOnly, SameSite=Lax cookie with a seven-day
  lifetime. The built-in strategy stores the token directly in its `accesstoken` table,
  with user_id and created_at. This differs from our original hashed-token scaffold.
  Treat database token values as credentials; do not log or expose them.
- Each login creates a session; multiple devices can stay logged in independently.
  Logout deletes only the presented token. Expiry blocks access but does not delete
  the account or its teams. Expired-token cleanup remains to be added.
- Browser mutations check Origin and Sec-Fetch-Site. The frontend and API share an origin.
  Production requires HTTPS, COOKIE_SECURE=true, and the actual APP_ORIGIN.
- Alembic now owns schema creation. Docker runs `alembic upgrade head` before the API.
  `0001_accounts` matches the library's account schema; `0002_teams` adds catalog/teams.
  No existing data was modified during implementation. For an existing database with
  the previous library-only `user` and `accesstoken` schema, first verify it matches
  `0001_accounts`, then run `alembic stamp 0001_accounts` before `alembic upgrade head`.
  Stamping records a baseline without executing it; it must not be used for an empty
  database or one with only the original custom `users`/`sessions` tables.
  Do not delete volumes or drop tables to resolve a migration error.

## Team data and API

`pokemon` stores current catalog records: PokéAPI ID, name, types/stats (PostgreSQL
JSONB), nullable sprite URL, and synced_at. Teams reference these stable IDs.
`teams` stores UUID, owner ID, name, and creation/update timestamps. `team_members`
uses (team_id, position) as its primary key, with a Pokemon foreign key. Position
must be 0-5; the API assigns consecutive positions from the submitted array. Duplicate
Pokemon and empty teams are allowed. Team deletion cascades to members, not Pokemon.

All team endpoints require a session. Ownership is taken from current_user; every
team query scopes by owner. Other users' teams return 404. Browser mutations enforce
the same origin rules as account actions; private responses use Cache-Control: no-store.

| Endpoint | Contract |
| --- | --- |
| GET /api/teams | Current user's teams with ordered member details; most recently saved first |
| POST /api/teams | Create; 201 with Location header and resolved team |
| GET /api/teams/{id} | One resolved team; 404 if absent or owned by someone else |
| PUT /api/teams/{id} | Replace the complete name and ordered lineup; 200 |
| DELETE /api/teams/{id} | Delete team and memberships; 204 |
| GET /api/pokemon | Public catalog page: items, total, limit, offset; q/name and type filters |
| GET /api/pokemon/{id} | Public catalog detail; 404 if absent |

POST and PUT both require `{"name":"Starters","pokemon_ids":[25,1,7]}`.
Names are trimmed and must be 1-80 characters. IDs must be positive integers, with
at most six entries. Unknown IDs return 422 with code UNKNOWN_POKEMON and the missing
IDs; malformed requests also return 422. Extra fields, including user_id, are rejected.
Responses include id, name, timestamps, and members with position and nested Pokemon.

Each save validates the catalog IDs, replaces membership rows, and commits atomically.
An error rolls back both name and membership changes. PUT and DELETE lock the owned
team row in PostgreSQL to serialize simultaneous edits; last successful save wins.
The backend suite now runs against both SQLite and PostgreSQL. PostgreSQL tests also
verify actual JSONB columns/queries and row locking. Per-test schemas isolate data,
including migration round trips and account-schema adoption. See TESTING.md.

The catalog starts empty; populate it with the explicit CLI command below. Tests
use controlled fixtures. The local development database was initially populated on
October 19, 2026: all 1,351 discovered PokéAPI records imported with zero failures.
This is local development data, not a deployed production database.

## PokéAPI ingestion

After migrations, from the repository root run:

```bash
docker compose run --rm api python -m app.ingest
```

This overrides the image's startup command, so migrations must already have run
(for example via `docker compose up --build`). For a first fresh setup without starting
the API, use `docker compose run --rm api alembic upgrade head` before ingestion.
For a sample, append `--limit 3`; this is explicitly reported as scope=sample and is
not a complete catalog. Without Docker, run `python -m app.ingest` from `backend`
with DATABASE_URL set. `python -m app.ingest --help` shows the sample option.

- Discover every `/pokemon` page, including alternate forms, before writing anything.
  Validate count consistency, repeated links, and expected PokéAPI URLs. A discovery
  failure aborts without writes. The HTTP client is shared and has explicit timeouts.
- Fetch at most five details concurrently. Retry connection/transport failures,
  429, and 5xx up to three total attempts; other HTTP errors and invalid data fail
  that record without retries. Backoff is 1s then 2s unless Retry-After specifies
  a delay (seconds or HTTP date). Requests for delays over 60s fail for later rerun
  rather than retrying early. Redirects are not followed.
- Normalize ID/name, one or two types in slot order, exactly six distinct base stats,
  and nullable front_default sprite URL. Missing required data, negative/non-integer
  stats, ID mismatches, invalid types, and invalid sprite URLs reject that record.
  Upstream fields the application does not use are ignored. No sprite images are downloaded.
- Save one validated record per short transaction. Insert by PokéAPI ID, update changed
  used fields in place, or refresh synced_at when unchanged. Keep memberships intact.
  Database writes are sequential while detail fetching is concurrent. Failures roll
  back only their own record; successfully committed records remain available.
- Progress goes to stderr; the final JSON summary goes to stdout with discovered,
  selected, scope, inserted, updated, unchanged, failed, failures by ID, and absent_ids.
  Full runs report locally stored IDs absent upstream but never delete them. Sample
  runs suppress absence reporting. Exit 0 means every selected record succeeded;
  partial/fatal failures exit 1; interruption exits 130. Rerun safely to retry.
- Manual imports and scheduled scans share a PostgreSQL advisory lock; overlapping
  attempts are audited and skipped before upstream requests. synced_at means last successful check, not when upstream data changed.
  There is no refresh HTTP endpoint and ingestion never runs inside the API. The separate
  scanner service runs immediately on its own startup, then at the configured interval.

Read `app/pokeapi.py` for the HTTP client and pure normalization, `app/catalog_sync.py`
for persistence, and `app/ingest.py` for CLI orchestration and summaries. These functions
will be reused by the change scanner. Each changed record and its history entry commit in the same transaction;
initial Pokémon inserts establish the baseline without history entries.

History decision: current tables remain simple, with a separate append-only change log
containing before/after values and detected_at. detected_at
records observation time, not the unknown upstream effective time. Full SCD2/as-of
catalog queries and team snapshot/restore are deferred. Catalog changes will not alter
team positions or point memberships at historical versions.

## Counter-team generation

Choose **View optimal counter team** for any nonempty editor lineup, including an
unsaved draft. The modal previews an equal-sized lineup and explains each opposing
slot's pairing, outgoing/incoming type effectiveness, and safe/risky status. Expand
method/stat details for the full scoring model. **Save as new team** creates a separate
team with the preview order; it never modifies or discards the source draft. Closing
without saving writes nothing. Generated teams use distinct catalog IDs; alternate
forms and legendary entries are eligible, and source members may also be candidates.

POST `/api/teams/counter-preview` accepts `{"pokemon_ids":[25,1,7]}` with 1–6 IDs and
requires authentication and the normal same-origin checks. It reads the local catalog,
returns no-store preview data, and performs no team writes. Duplicate opposing members
remain separate slots. Unknown IDs return 422; a catalog with fewer distinct entries
than opposing slots returns 409. There are no network calls during generation.

The exact objective, compared lexicographically, is:

1. Maximize the number of safe assigned matchups: outgoing effectiveness >= 2× and
   the opponent's best return effectiveness <= 1×.
2. Maximize the sum of (outgoing effectiveness minus incoming effectiveness).
3. Maximize the sum of relative-stat scores. Each component below is an integer
   from 0 to 1,000; components sum to 0–3,000 per matchup. Zero versus zero is neutral.
4. If all scores tie, choose the lexicographically lowest candidate ID list in
   opposing-slot order, making results deterministic.

For stats, let R(a,b) = round-half-up(1000*a/(a+b)), or 500 if both are zero.
Attack potential is max(R(candidate Attack, opposing Defense), R(candidate Sp. Atk,
opposing Sp. Def)). Durability is the integer-floor average of R(candidate HP *
candidate Defense, opposing HP * opposing Attack) and its special-stat equivalent.
Speed is R(candidate Speed, opposing Speed). This is an explicit base-stat proxy,
not the game's damage formula; stats cannot outweigh the first two objectives.

`backend/app/counters.py` uses a bitmask dynamic program over candidates and opposing
slots, O(catalog_size * n * 2^n), n <= 6, without pruning or greedy selection. CPU work
runs outside the async request loop. The result is optimal under this additive assigned-
matchup model, not a claim of optimal real-battle strategy or team switching synergy.

The model assumes each side can use attacks of either own type, taking its best type
against both defending types. Defensive multipliers multiply; attacking types are
alternatives, never multiplied together. Immunities remain zero. Moves, abilities,
items, levels, and switching are excluded. Equal assumed same-type attack bonuses are
omitted; displayed numbers are type effectiveness, not damage or win probabilities.

The API reads the active chart from PostgreSQL on each preview, returning its SHA-256
version plus `safe-coverage-v1`. Migration 0003 seeds a frozen PokéAPI snapshot from
`backend/migrations/data/type_chart_v1.json`; provenance and observation time are in
that file. The scanner fetches and validates all 18 current type rows, then replaces
the chart and appends per-attacking-type history in one transaction. A missing or
invalid row leaves the entire old chart intact. No API restart is needed. The bundled
app snapshot remains the pure optimizer's offline/test default. Historical game charts
and nonstandard types remain outside the model.

## Scanner and history

The `scanner` Compose service uses the backend image with a separate command:
`python -m app.scanner --schedule`. It starts after the API has applied migrations
and passed its health check. The API process never starts schedules or scrapes data.
Scans use only PokéAPI: Pokémon details and the 18 standard type relationships.

Configure `.env` (defaults shown in `.env.example`), then recreate affected services:

- `CATALOG_SCAN_INTERVAL_HOURS=24`: positive integer; scan immediately on scanner
  startup, then wait this interval after completion. Restarting starts a fresh scan.
- `CHANGE_ALERT_WINDOW_DAYS=7`: positive integer, validated and available in backend
  settings for the next alert increment. It does not prune history or affect scans.

Run once with `docker compose run --rm scanner python -m app.scanner`.
The existing `python -m app.ingest [--limit N]` command remains a Pokémon-only import,
now sharing scan audit and overlap protection. Manual import stdout retains its
Pokémon counts with a status field. A one-shot failed/partial scan exits nonzero;
overlapping attempts are audited as skipped and exit successfully.

A session-level PostgreSQL advisory lock protects the entire scan. All scan writes
use the physical connection holding that lock, with short per-record transactions;
connection loss aborts writes rather than silently reconnecting without a lock.
Fetches remain bounded/retried by the existing importer. The scheduler releases the
lock while waiting, handles termination by cancelling current work, and continues
scheduled attempts after an ordinary scan failure. Abruptly stopped `running` audits
are marked interrupted by the next lock holder; committed records remain intact.

`scan_runs` records start/end, outcome, resource summaries, per-ID failures, and absent
IDs. Interrupted runs may have only completed-resource summaries. `catalog_changes`
appends entity kind/key/name, detected time, changed field paths and before/after
values, plus the originating scan ID. New Pokémon establish a baseline; only actual
used-field differences create history. Repeats do not duplicate history. Failed
fetches, invalid details, and absent upstream IDs never delete local data. Successful
records still commit when others fail; per-record catalog/history changes are atomic.

Alerts and the isolated deterministic demo are intentionally the next increments;
there is no alert/history HTTP endpoint or frontend in this increment. Type-chart
changes can later be matched to the involved attack/defense types in saved teams.

## Review and remaining scope

Read backend/app/models.py (tables), team_schemas.py (public contracts), teams.py
(ownership, validation, atomic save), catalog.py (catalog reads), and the two migration
revisions. Authentication configuration moved to auth.py; db.py owns database sessions,
settings.py holds environment settings, security.py enforces origins, and main.py
assembles routers. The existing authentication API behavior is preserved.

For the frontend, read `frontend/src/api.ts` (HTTP requests and error translation),
then `frontend/src/App.tsx` (session check, form actions, account screens),
`frontend/src/TeamBuilder.tsx` (catalog requests and explicit-save draft state),
`frontend/vite.config.ts` (development proxy), and `frontend/nginx.conf` (Compose proxy).
No frontend authentication package or global state library is needed for these screens.

Next: alerts and deterministic demo, session cleanup, login rate limiting before public deployment,
deployment, and final one-page README. Password recovery and
email verification are outside scope. Health currently reports process liveness only.
