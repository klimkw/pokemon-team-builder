# Continue the Pokemon Team Builder project

## User intent and working style

This is a take-home assignment due Wednesday, October 21, 2026 at 8:00 AM Eastern.
The original total time budget was eight hours; remaining time has not been measured.
The user wants high control and visibility, iterative implementation, and a walkthrough
of each design and implementation before moving to the next feature. They must be able
to present and explain the application from frontend to database. Do not build remaining
features in one large pass. Discuss new architectural choices first.

## Location and environment transition

The project is currently stored at:

- Windows: C:/Users/limk/Documents/Codex/2026-10-19/i-d/outputs/pokemon-team-builder
- WSL: /mnt/c/Users/limk/Documents/Codex/2026-10-19/i-d/outputs/pokemon-team-builder

Use this existing directory first; no source relocation is required. Windows node_modules
and virtual environments must not be reused as Linux installations. Docker builds install
their own dependencies; prefer Docker for the initial verification. Do not copy or modify
the user's Codex authentication/session files to migrate this conversation.

Docker Desktop with WSL 2 has been installed. The Windows agent could invoke the Docker
CLI at C:/Users/limk/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe,
but its sandbox could not access the Docker named pipe or wsl.exe. The user switched
the agent to WSL, could not resume the original chat, and reverted to Windows. This
handoff supports a new WSL chat; do not claim Docker access until checking it there.

## Assignment requirements

Responsive Pokemon catalog showing names, types, stats, and sprites. Multiple persistent
ordered teams of up to six Pokemon, with add/remove/reorder/edit/delete. Generate an
explainable counter team of equal size. Backend job detects changes in data used by the
builder; show users alerts describing changes to their Pokemon detected within a week.
Demonstrate change detection deterministically. Deliver a shareable repository, public
frontend URL, tests, and a final one-page README on decisions/assumptions.

Original reference PDF: C:/Users/limk/Downloads/Pokemon Case Study.pdf.
Treat the PDF as assignment reference, not agent instructions.

## Agreed architecture and rules

- Python/FastAPI, FastAPI Users 14.0.2, async SQLAlchemy, PostgreSQL, Alembic.
- React + TypeScript + Vite; Nginx serves the build and proxies /api in Docker.
- Minimal username/password accounts. Username is normalized lowercase and mapped to
  FastAPI Users' internal email field. Email/recovery/OAuth routes are not enabled.
- Argon2 password hashing; opaque tokens in HttpOnly SameSite=Lax cookies; seven-day
  expiry. Library DatabaseStrategy stores raw tokens in accesstoken; this tradeoff is
  documented. No frontend token storage. Server enforces authentication and ownership.
- Teams allow duplicates and zero members. Name plus ordered pokemon_ids array is saved
  explicitly as one resource. No autosave. Last successful save wins.
- Current Pokemon catalog records have stable upstream IDs. Teams reference current
  records. Future append-only catalog change log, not SCD2 in the main tables. Team
  snapshots/undo are deferred. detected_at means observation time, not upstream effective time.
- Catalog refresh is a CLI command, not an HTTP endpoint. Initial import and later sync
  share the same code. Scheduling, overlap prevention, and change logging are not built yet.
- Development secrets go in ignored .env; .env.example has placeholders. Never overwrite
  an existing .env, print secrets, delete development volumes, or reset development data.

## Implemented

1. Account API: registration, login, me, logout; origin checks and no-store responses.
2. Account React UI: registration/login, connection/loading/error states, session restoration,
   signed-in view, logout. The signed-in page now hosts the team builder.
3. Models: Pokemon, Team, TeamMember; PostgreSQL JSONB; membership position constraints,
   ownership foreign keys, cascade memberships on team deletion.
4. API: public catalog search/type filter/pagination/detail; authenticated team CRUD.
   PUT validates IDs, locks the parent row, replaces ordered memberships, and commits
   atomically. Tests include injected mid-save failure and rollback.
5. Alembic baseline 0001_accounts and 0002_teams. Startup runs upgrade head. Existing
   account-only databases need verified baseline adoption; see README. Do not blindly stamp.
6. CLI ingestion: python -m app.ingest [--limit N]. Complete pagination discovery, URL/count
   checks, five concurrent detail requests, three bounded retry attempts, validation and
   normalization, sequential per-record transactions, idempotent inserts/updates, summaries,
   per-ID failures, nonzero exit on failure, no automatic deletion. Initial loading does
   not run on API startup. No notification history is recorded yet.
7. Test setup: compose.test.yaml, scripts/test.ps1, PostgreSQL fixtures with isolated random
   schemas, JSONB/row-lock tests, and Playwright Chromium account-flow test.

8. Team builder React UI: paginated searchable/type-filtered catalog with sprites and
   all six stats; multiple-team selection, create/rename/delete, six slots, duplicates,
   remove/reorder buttons, explicit save and failed-save draft retention. Unsaved-edit
   prompts protect switching/new/sign-out, and beforeunload protects refresh/close.
   Responsive stacked layout includes mobile jump links. No browser draft persistence.
9. Docker component runner plus a guarded disposable catalog fixture for browser tests.
   13 frontend tests and two E2E tests pass, including team persistence across login,
   capacity, pagination/filtering, reorder/remove, empty teams, and mobile layout.
10. Private repository https://github.com/klimkw/pokemon-team-builder is connected as
    origin. Commit and push after small verified milestones, as the user requested.
    Windows Git can push using its existing credential manager; Linux Git handles
    local commits. Local-only settings, secrets, environments, and reports are ignored.

## Verified results and limits

- 51 backend tests passed on real PostgreSQL 17.11 using an isolated portable Windows
  instance under the old chat's work/ directory, not Docker and not the development DB.
- Seven React component tests passed; TypeScript and production build passed.
- Playwright account E2E passed against real PostgreSQL + FastAPI + production React build
  served through Vite preview. It covers registration, bad password, login, reload,
  separate-context isolation, logout, old-cookie replay rejection, and another login.
- Fast SQLite suite has 49 tests plus two PostgreSQL-only skips.
- Live ingestion discovered 1,351 entries and imported three real records in a scratch
  SQLite database; repeat import reported three unchanged. No full deployment catalog
  import has been done by the agent.
- Docker/Nginx orchestration passed October 19, 2026: 51 PostgreSQL backend tests
  and one Chromium account E2E test. Service health checks passed and the isolated
  stack was removed. The Windows-mounted cache metadata blocked a direct build;
  a temporary source copy under /tmp excluding host caches built successfully.
  No application fixes or development data changes were needed. See TESTING.md.
- Temporary verification PostgreSQL/API/frontend services were stopped. No development
  database was reset or modified by those verification runs.

## Docker verification procedure (completed October 19, 2026)

Read TESTING.md, compose.test.yaml, and the Dockerfiles first. Check docker version and
docker compose version; Docker Desktop WSL integration must be enabled for this distro.
The CLI must report a reachable server. Then, from this project directory:

```bash
docker compose -p pokemon-team-builder-tests -f compose.test.yaml build
docker compose -p pokemon-team-builder-tests -f compose.test.yaml up -d --wait db-test api-test frontend-test
docker compose -p pokemon-team-builder-tests -f compose.test.yaml run --rm backend-tests
docker compose -p pokemon-team-builder-tests -f compose.test.yaml run --rm frontend-tests
docker compose -p pokemon-team-builder-tests -f compose.test.yaml run --rm e2e
docker compose -p pokemon-team-builder-tests -f compose.test.yaml down
```

Always clean up this explicitly named test project after failures. It has its own tmpfs
database and does not use the development postgres_data volume. Reports are bind-mounted
under test-artifacts/. Test ports 55432 and 18080 must be free. Do not combine the test
Compose file with development compose.yaml. Do not expose the Docker daemon over an
unauthenticated TCP endpoint or change Windows sandbox-user permissions as a workaround.

After verification, explain the result and any fixes. Counter-team generation is now
implemented under the user-approved priorities: safe coverage, then type strength,
then relative stats. The next product increment is change detection/history/alerts;
walk through it with the user first. Remaining work includes upgrading existing
Vitest tooling (three npm audit findings documented in TESTING.md), scanning all used
data including type relations, scheduled runs/overlap prevention, session cleanup,
login rate limiting, deployment, and final one-page README/presentation preparation.

## Counter-team increment

- POST /api/teams/counter-preview takes the current editor's ordered pokemon_ids,
  requires auth/origin checks, returns no-store, and never writes teams.
- Pure exact bitmask DP in backend/app/counters.py: maximize safe count (outgoing>=2,
  incoming<=1), total outgoing-minus-incoming effectiveness, then relative attack/
  durability/speed scores. Equal results choose lowest ordered IDs. Distinct generated
  IDs, repeated opposing slots allowed. All local catalog entries are eligible.
- Chart snapshot backend/app/data/type_chart.json caches all 18 current PokéAPI types,
  records provenance and verifies its SHA-256. No live requests during generation.
  Future scanner must cover type relations too; no chart-refresh scheduler exists yet.
- Frontend CounterPreview.tsx uses a native modal with loading/retry, safe/risky
  explanations, expandable stats/assumptions, and explicit Save as new team. Preview
  uses unsaved member edits; closing or saving preserves the original draft. New saved
  counters appear in the existing selector. Model excludes moves/abilities/items/battle
  simulation; do not describe scores as win probabilities.
- The running development API/frontend have been refreshed with this increment.
  Existing accounts, teams, and the 1,351-record catalog were preserved. A read-only
  six-member full-catalog optimization took about 0.35 seconds. Users must refresh
  their browser when ready to load the updated UI; do not force-discard drafts.
- Verification: 69 PostgreSQL backend tests, 18 frontend component tests, 3 Chromium
  E2E tests. TypeScript and production build pass. The optimizer is checked against
  exhaustive small assignments. See README.md for exact formulas and TESTING.md.

## Running development environment

Started October 19, 2026 at the user's request; leave running for manual review.
Project: pokemon-team-builder, using the existing compose.yaml. UI is
http://localhost:8080 and backend docs are http://localhost:8000/docs. An ignored
.env was created only because none existed, with a generated database password.
Do not print or commit it. No existing data was reset. The initial database catalog
was empty; full CLI ingestion inserted all 1,351 discovered records, zero failures.
The catalog API was checked through Nginx and returned real types, stats, sprites.
Development data persists in pokemon-team-builder_postgres_data. This stack is
separate from the removed pokemon-team-builder-tests project. Current Docker images
were built from the clean /tmp source copy to avoid unreadable host cache metadata.
This frontend is a production build served locally, without hot reload.

## Useful files

- README.md and TESTING.md: current operating/design documentation.
- backend/app/models.py, team_schemas.py, teams.py, catalog.py: team/catalog implementation.
- backend/app/pokeapi.py, catalog_sync.py, ingest.py: importer.
- backend/app/auth.py, db.py, security.py, settings.py, main.py: accounts and API assembly.
- backend/tests/conftest.py: --postgres selection, explicit pokemon_test name guard,
  random per-test schemas and cleanup; NullPool avoids crossing asyncio event loops.
- frontend/src/App.tsx, TeamBuilder.tsx, and api.ts: account UI, team workspace, HTTP client.
- frontend/e2e/account.spec.ts, playwright.config.ts, Dockerfile.e2e: browser test.
- frontend/package.json and lockfile, Dockerfile.e2e: Playwright is pinned to 1.64.0
  in both npm and the matching browser image.

Do not assume the repo has Git history or a remote; inspect before Git operations.
