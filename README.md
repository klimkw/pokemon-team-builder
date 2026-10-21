# Pokemon Team Builder

Take-home project built in reviewable increments. Current increment: compact workspace, advanced Pokédex filters, editable profiles and unread alerts,
alongside the catalog, persistent teams, explainable counters, and change history.

## Run and test

Copy `.env.example` to `.env` and choose a long random alphanumeric database password.
Run `docker compose up --build`, then open http://localhost:8080 for the application.
API documentation is available at http://localhost:8080/docs and http://localhost:8000/docs.
Sign in through the app first; admin operations reuse your session. If you already have a `.env`
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
`npm run build`. 127 backend tests pass against PostgreSQL; the fast SQLite option
passes 112 with 15 PostgreSQL-only skips. All 23 frontend component tests pass. Six
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
docker compose run --rm api python -m app.jobs.ingest
```

This overrides the image's startup command, so migrations must already have run
(for example via `docker compose up --build`). For a first fresh setup without starting
the API, use `docker compose run --rm api alembic upgrade head` before ingestion.
For a sample, append `--limit 3`; this is explicitly reported as scope=sample and is
not a complete catalog. Without Docker, run `python -m app.jobs.ingest` from `backend`
with DATABASE_URL set. `python -m app.jobs.ingest --help` shows the sample option.

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
  The admin refresh HTTP endpoint queues work; ingestion never runs inside the API. The separate
  scanner service runs immediately on its own startup, then at the configured interval.

Read `app/services/pokeapi.py` for the HTTP client and pure normalization, `app/services/catalog_sync.py`
for persistence, and `app/jobs/ingest.py` for CLI orchestration and summaries. These functions
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
without saving writes nothing. Generated teams allow duplicate catalog IDs, matching the source-team rules. Alternate
forms and legendary entries are eligible, and source members may also be candidates.

POST `/api/teams/counter-preview` accepts `{"pokemon_ids":[25,1,7]}` with 1–6 IDs and
requires authentication and the normal same-origin checks. It reads the local catalog,
returns no-store preview data, and performs no team writes. Duplicate opposing members
remain separate slots. Unknown IDs return 422; even a one-entry catalog can fill all six counter slots. There are no network calls during generation.

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

`backend/app/services/counters.py` independently maximizes the same score tuple per
opposing slot in O(catalog_size * n), n <= 6. This is an exact global optimum because
scores are additive and candidates can be reused. Six identical opponents receive six
copies of the same best counter. CPU work runs outside the async request loop; this
is an assigned-matchup model rather than an optimization of switching or team synergy.

The model assumes each side can use attacks of either own type, taking its best type
against both defending types. Defensive multipliers multiply; attacking types are
alternatives, never multiplied together. Immunities remain zero. Moves, abilities,
items, levels, and switching are excluded. Equal assumed same-type attack bonuses are
omitted; displayed numbers are type effectiveness, not damage or win probabilities.

The API reads the active chart from PostgreSQL on each preview, returning its SHA-256
version plus `safe-coverage-v2-duplicates`. Migration 0003 seeds a frozen PokéAPI snapshot from
`backend/migrations/data/type_chart_v1.json`; provenance and observation time are in
that file. The scanner fetches and validates all 18 current type rows, then replaces
the chart and appends per-attacking-type history in one transaction. A missing or
invalid row leaves the entire old chart intact. No API restart is needed. The bundled
app snapshot remains the pure optimizer's offline/test default. Historical game charts
and nonstandard types remain outside the model.

### Auditable selection code

The core selection uses the actual lexicographic tuple `(safe, 4 * type_strength,
stats_score)`, followed by the lowest ID. Duplicates make slots independent:

```python
ids = [max(by_id, key=lambda identifier: (scorer(by_id[identifier], opponent).objective, -identifier))
       for opponent in opponents]
```

This excerpt is from `backend/app/services/counters.py`. A safe pairing always beats
an unsafe one, regardless of stats. Example checked by unit tests: a Pokémon with all
six base stats at 100 against one with all six at 50 scores Attack 667 + Durability
800 + Speed 667 = 2,134. The preview's **Show score arithmetic** substitutes actual
pair inputs into these formulas. The full [model guide](frontend/src/docs/counter-model.md)
contains damage calculations and limitations; scores are never win probabilities.

### Shared comparison and illustrative replay

The preview uses the same Pokémon card component as the Pokédex, pairing your Pokémon
on the left with its counter on the right. **Run matchup simulation** starts independent,
deterministic paired duels. Advance a turn, jump to results or restart; expand formulas
and logs to audit damage and HP. Results count duel wins, draws and stalemates, not a
real team-battle win probability. Selection remains unchanged by replay outcomes.

The complete, repo-managed [scoring and simulation guide](frontend/src/docs/counter-model.md)
is rendered at `/counter-method` and linked from the preview. It explains the exact
optimizer, stat rounding, own-type attack assumptions, the custom damage formula,
speed ties, immunities, the 200-turn cap and limitations. Edit that Markdown file to
update the web page; the guide is bundled locally and offers a Markdown download.
`backend/app/services/battle.py` implements `paired-base-stats-v1`; its values are
returned with the preview and reused throughout replay without refetching data.
No migrations, upstream battle-data calls or simulation dependencies are introduced.

## Scanner and history

The `scanner` Compose service uses the backend image with a separate command:
`python -m app.jobs.worker --schedule`. It starts after the API has applied migrations
and passed its health check. The API process never starts schedules or scrapes data.
Scans use only PokéAPI: Pokémon details and the 18 standard type relationships.

Configure `.env` (defaults shown in `.env.example`), then recreate affected services:

- `CATALOG_SCAN_INTERVAL_HOURS=24`: positive integer; scan immediately on scanner
  startup, then wait this interval after completion. Restarting starts a fresh scan.
- `CHANGE_ALERT_WINDOW_DAYS=7`: positive integer, validated and available in backend
  settings for the next alert increment. It does not prune history or affect scans.

Run once with `docker compose run --rm scanner python -m app.jobs.scanner`.
The existing `python -m app.jobs.ingest [--limit N]` command remains a Pokémon-only import,
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

## Recent-change alerts and reproducible demo

The header bell opens recent changes to Pokémon in your current saved teams.
Its red badge counts unread events; the tray is closed by default. Displayed events
are marked read on the server, preserving that state across sessions.
GET `/api/alerts` groups affected Pokémon, owned teams, and duplicate slots; it includes
before/after values, detection timestamps, pagination and the latest scanner status.
Type-chart changes match both a Pokémon's attacking types and its defensive types.
The backend's `CHANGE_ALERT_WINDOW_DAYS` controls the window (default seven days).
Alerts refresh on saved-team changes or with **Refresh alerts**; drafts are preserved.
Per-user read markers persist unread state; history is retained independently of the window.

Admin controls in the same app provide POST `/api/admin/demo/changes`,
POST `/api/admin/demo/reset`, POST `/api/admin/refresh`, and GET `/api/admin/jobs`.
Writes return a durable job ID; the separate scanner worker performs the work.
Manual changes use your existing full catalog and saved teams, and alerts label them
as demo changes. Reset restores only recorded fields and removes only tagged demo
history. Full refresh records real source differences normally, including reversals.

See [the API-doc walkthrough](agent-process/05-admin-scanner-controls.md) for admin
setup, example requests, status polling and reset semantics. Local Compose enables
manual controls explicitly; standalone application defaults disable them. Older
isolated fixture tooling remains in compose.demo.yaml but is not needed for this flow.

## Review and remaining scope

The backend separates responsibilities under `backend/app/`:

- `api/`: HTTP routes, authentication, and request security.
- `db/`: SQLAlchemy table models and database engine/session setup.
- `services/`: counter-team scoring, upstream clients, and catalog/history updates.
- `jobs/`: manual imports and the separately scheduled scanner.
- `schemas/`: shared validated request and response contracts.
- `main.py` and `settings.py`: application assembly and environment settings.

Alembic's configuration and migration history stay in `backend/alembic.ini` and
`backend/migrations/`. PostgreSQL remains its own Compose service; the API and scanner
share the same database models and session setup. Existing `app.ingest` and
`app.scanner` commands remain compatibility entry points; prefer `app.jobs.ingest`
and `app.jobs.scanner` for new commands.

For the frontend, read `frontend/src/api.ts` (HTTP requests and error translation),
then `frontend/src/App.tsx` (session check, form actions, account screens),
`frontend/src/TeamBuilder.tsx` (catalog requests and explicit-save draft state),
`frontend/vite.config.ts` (development proxy), and `frontend/nginx.conf` (Compose proxy).
No frontend authentication package or global state library is needed for these screens.

Next: public hosting, session cleanup, login rate limiting before public deployment,
deployment, and final one-page README. Password recovery and
email verification are outside scope. Health currently reports process liveness only.


## Workspace controls

The Pokédex supports 12/24/48/96 records per page, multiple types with any/all matching,
and inclusive range sliders for each base stat. Index/stat sorting is applied before
pagination. Type badges and six-stat displays are shared with the selected team. Filters combine with search and reset
to the first page when changed. The profile button opens account controls and your
saved-team list. Username/password changes require the current password; a new password
revokes existing sessions. Team drafts remain intact while viewing Profile.
See [the UX walkthrough](agent-process/06-workspace-ux.md) for API and unread semantics.

## Secret handling before hosting

Local Compose reads the ignored root `.env` and injects database credentials into
backend/scanner runtime environments. Only `.env.example` is tracked. Build contexts
exclude `.env` variants, and the frontend needs no server-side credentials. This is
local configuration, not an encrypted secret vault; operators with container access
can inspect runtime environments. PokéAPI requires no API key. Authentication uses
opaque database-backed sessions rather than a JWT signing secret; session tokens
are stored directly in the database by the current library strategy, a documented
trade-off. Passwords are hashed, and the session cookie is HttpOnly/SameSite=Lax.

At hosting time, use the provider's managed runtime secrets/environment settings,
fresh production credentials, restricted access and a documented rotation procedure.
Set the correct HTTPS APP_ORIGIN and COOKIE_SECURE=true. Keep demo controls disabled
unless deliberately enabled for a restricted reviewer/admin workflow. Do not put
credentials in Vite variables, Docker build arguments, source code or screenshots.
We have not selected/configured a hosted secret store yet. Reference:
[OWASP secrets-management guidance](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

The header **App info** popup reads `/api/info`, an explicit allowlist of public version,
model, catalog-count and refresh timestamps/settings. It never returns database URLs,
credentials, user data, job payloads, scanner summaries or raw errors. The release
version comes from backend/pyproject.toml; it is not a commit counter. Latest live
refresh and last successful live refresh are separate, excluding manual/sample runs.
