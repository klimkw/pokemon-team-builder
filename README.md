# Pokemon Team Builder

Take-home project built in reviewable increments. Current increment: responsive catalog
and persistent team editor, verified through Docker and real-browser tests.

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

From `backend`, install `pip install -r requirements-dev.txt` and run `python -m pytest tests -q`.
From `frontend`, use Node 22.12+ (Node 24 recommended), run `npm ci`, `npm test`, and
`npm run build`. Fifty-one backend tests pass against PostgreSQL; the fast SQLite run has
49 passes and two PostgreSQL-only skips. All 13 frontend component tests pass. Both
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
- Run one importer at a time. Cross-process overlap prevention is deferred until
  scheduling. synced_at means last successful check, not when upstream data changed.
  There is no refresh HTTP endpoint and ingestion never runs automatically at API startup.

Read `app/pokeapi.py` for the HTTP client and pure normalization, `app/catalog_sync.py`
for persistence, and `app/ingest.py` for CLI orchestration and summaries. These functions
will be reused by the change scanner. The future change-log insert belongs in the same
transaction as a changed catalog record; initial inserts establish the baseline.

History decision: keep current tables simple. Add an append-only Pokemon change log
with before/after values and detected_at when implementing notifications. detected_at
records observation time, not the unknown upstream effective time. Full SCD2/as-of
catalog queries and team snapshot/restore are deferred. Catalog changes will not alter
team positions or point memberships at historical versions.

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

Next: explainable counter teams,
change scanner/alerts/demo, session cleanup, login rate limiting before public deployment,
deployment, and final one-page README. Password recovery and
email verification are outside scope. Health currently reports process liveness only.
