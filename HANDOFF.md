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
  share the same code. Scheduling, overlap prevention, and change history are implemented;
  user alerts and the deterministic demo are the next increments.
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
6. CLI ingestion: python -m app.jobs.ingest [--limit N]. Complete pagination discovery, URL/count
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

After verification, explain the result and any fixes. Scanner/history are now implemented;
alerts and the deterministic demo are the next increments. Walk through each before
implementing. Remaining work includes the known Vitest tooling advisories, alert API/UI,
isolated demo, session cleanup, login rate limiting, deployment, and final one-page README.

## Scanner/history increment

- Separate Compose scanner service: python -m app.jobs.scanner --schedule, startup scan then
  CATALOG_SCAN_INTERVAL_HOURS after completion (default 24). CHANGE_ALERT_WINDOW_DAYS
  defaults to 7 and is available for the upcoming alert queries. Both require positive
  integers. Never prune history based on the alert window.
- Migration 0003 adds scan_runs, append-only catalog_changes, and singleton type_chart.
  Existing accounts, teams and catalog are preserved. Frozen migration snapshot seeds
  the previously observed type baseline; it must not be edited to update active data.
- Scanner validates/fetches Pokémon and all 18 PokéAPI type rows. Each Pokémon update
  and field-level history entry commit together. Whole-chart replacement and per-type
  history commit together only after complete validation. Initial Pokémon inserts do
  not generate change history; repeated identical scans create no duplicate history.
- Manual app.jobs.ingest and scheduled scans share one PostgreSQL advisory lock. All writes
  use its physical connection; a lost connection cannot silently continue without the
  lock. Overlap attempts are audited as skipped. Shutdown cancellation and stale running
  audit recovery are implemented; committed records survive interruptions.
- Counter API reads the active DB chart per request, without live upstream calls or an
  API restart after chart changes. Pure optimizer tests can still use the bundled chart.
- The first live development scan succeeded: 1,351 Pokémon unchanged, 18 type rows
  unchanged, zero failures/history entries. Existing two teams and one account were
  preserved. Scanner remains running and waits 24 hours after completion.
- Verification: 93 PostgreSQL backend tests, plus existing browser regressions. No alerts,
  notification endpoints, or user-facing deterministic demo are implemented yet.

## Counter-team increment

- POST /api/teams/counter-preview takes the current editor's ordered pokemon_ids,
  requires auth/origin checks, returns no-store, and never writes teams.
- Pure exact bitmask DP in backend/app/services/counters.py: maximize safe count (outgoing>=2,
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

## Python tooling and process documentation

The backend uses uv project management: pyproject.toml, committed uv.lock, and Python
3.12 in .python-version. Requirements files were replaced. Both Dockerfiles copy
pinned uv 0.13.3 by digest and install locked image-local environments; runtime omits
dev dependencies, tests include the dev group. Host commands from backend use
uv sync --locked and uv run --locked. All 43 prior installed versions were preserved
in the lock and installed test environment during migration. Runtime inspection and
offline lock checks passed. uv-built images passed 93 PostgreSQL tests, 84 SQLite tests
with 9 skips, and all 3 browser regressions. Development API/scanner now use the uv
environment; existing data and migration head 0003 were preserved. Use
uv run --locked python -m pytest for tests. Do not reuse Windows .venv inside Linux.

agent-process/ contains a detailed chronological build journal, PostgreSQL/Alembic
walkthrough, and uv guide. Continue recording completed increments there. Early work
before the initial commit is attributed to the handoff rather than invented commits.
Keep these process docs separate from the eventual one-page submission README.

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
This frontend is a production build served locally, without hot reload. The separate
scanner service is now enabled with a 24-hour interval; the alert-window setting is 7
days. Migration 0003 adds history and the active chart without resetting existing data.

## Useful files

- README.md and TESTING.md: current operating/design documentation.
- backend/app/db/: SQLAlchemy models and engine/session setup.
- backend/app/api/: routes, authentication, and request security.
- backend/app/schemas/: shared request/response contracts.
- backend/app/services/: scoring, upstream clients, catalog/history synchronization.
- backend/app/jobs/: import and scanner orchestration; Compose runs app.jobs.scanner.
- backend/app/settings.py and main.py: settings and API assembly.
- backend/migrations/: unchanged Alembic revision history.
- backend/tests/conftest.py: --postgres selection, explicit pokemon_test name guard,
  random per-test schemas and cleanup; NullPool avoids crossing asyncio event loops.
- frontend/src/App.tsx, TeamBuilder.tsx, and api.ts: account UI, team workspace, HTTP client.
- frontend/e2e/account.spec.ts, playwright.config.ts, Dockerfile.e2e: browser test.
- frontend/package.json and lockfile, Dockerfile.e2e: Playwright is pinned to 1.64.0
  in both npm and the matching browser image.

Do not assume the repo has Git history or a remote; inspect before Git operations.


## Backend organization

The backend is separated into app/api, app/db, app/services, app/jobs, and shared
app/schemas. Database sessions are imported as `from app.db import session as db`;
models are in app.db.models. API/main and jobs share that canonical session module,
including the test fixture's engine/session factory overrides. Avoid re-exporting
copied engine/session objects from db/__init__.py. Current CLI commands use
app.jobs.ingest and app.jobs.scanner; thin app.ingest/app.scanner wrappers preserve
existing commands and exit codes. app/main.py remains the ASGI entry point.

Alembic env.py uses the new metadata imports; historical revisions are unchanged.
The type-chart file remains app/data/type_chart.json; its service loader resolves
from the app directory. Docs and tests use current paths. The refactor passed 93
PostgreSQL tests, 84 SQLite tests (9 skips), 18 frontend tests, and 3 Chromium flows.
Reports: test-artifacts/backend-refactor/. Test stack cleaned up. Development API
and scanner refreshed; health and alembic check passed. Full startup scan succeeded,
1,351 Pokémon and all 18 type rows unchanged; 2 teams, 1 account, 0 changes and
migration head 0003 preserved. The clean build source is /tmp/pokemon-backend-refactor.
Next: public hosting, a hosted browser-controlled demo adaptation, and the final one-page README.


## Latest increment: alerts and deterministic demo

Alerts and the local deterministic demo are implemented. GET /api/alerts authenticates
and matches recent changes to the current user's saved team memberships, grouping
repeated slots and teams. It matches Pokémon IDs and both attacking/defensive type
relevance, includes field differences/detection times/latest scan status, paginates,
and sets no-store. The configurable window includes its exact cutoff and excludes
future timestamps. History is not pruned and there are no unread/dismissal flags.
Current membership determines visibility, including changes predating a team save.

The React Alerts panel refreshes after saved team changes and explicitly with Refresh
alerts. It preserves drafts and reports loading, empty, errors, retry and scan freshness.
DEMO_MODE labels the fixture environment; COOKIE_NAME is configurable with the existing
pokemon_session default. Demo uses pokemon_demo_session to avoid login collisions.

compose.demo.yaml is standalone, project pokemon-team-builder-demo, ports 8081/8001,
private tmpfs PostgreSQL pokemon_demo, fixture credentials, no development volumes.
app.jobs.demo requires DEMO_MODE=true and exactly that PostgreSQL database name at the
CLI boundary. Baseline/change/repeat use fixture HTTP responses with the real scanner,
normalization, atomic history and lock. Baseline yields 0 changes; change yields 2
(Bulbasaur Attack 49->60, fire damage_to.grass 2->1); repeat remains at 2, no writes to
history. CLI asserts counts; baseline refuses to reset an already-changed demo. There
is no demo HTTP mutation endpoint. See agent-process/04-alerts-and-demo.md for commands.

Verification: 106 PostgreSQL tests, 96 SQLite tests (10 skips), 22 component tests,
3 ordinary Chromium flows and a separate demo Chromium flow. The normal E2E runner
skips demo.spec.ts; run it explicitly with E2E_DEMO=true on the demo network after
change/repeat. Browser evidence is under test-artifacts/alerts/ and alerts-demo/.
The demo browser selector was corrected to scope Sign in to its form. No application
behavior fixes were needed. Clean build source: /tmp/pokemon-alerts-demo.

The user asked about free public hosting during implementation. We recommended a
guided browser demo with per-visitor temporary isolated scenario data, reusing the API
and DB server, and a small request-triggered fixture scan. This is future deployment
work, not a hosted capability already built. Keep the full catalog scanner a separate
job. Do not expose a shared reset endpoint that changes the live catalog or other
visitors' scenario. Public deployment and final one-page README are still outstanding.


Development API/frontend/scanner refreshed with tested images. The ordinary app
remains http://localhost:8080. Demo is intentionally left running at
http://localhost:8081, docs at :8001/docs; login demo_trainer /
Demo-only-password-2026 (fixture credentials only). It is at the changed/repeated
stage with 2 alerts. Its saved lineup was restored after browser testing. Demo API
APP_ORIGIN has been restored to http://localhost:8081 for manual use. Leave the
owner's browser/drafts alone; they can refresh when ready for the rebuilt frontend.

Final smoke checks confirmed 1,351 catalog records, 2 teams, 1 account, 0 development
change rows and migration head 0003 unchanged; refreshed scanner succeeded. Demo login
through its localhost:8081 origin returned its distinct session cookie and 2 no-store
alerts with is_demo=true. The demo browser test restores the original saved lineup.


## Current direction: same-app admin docs controls (supersedes separate demo)

The user explicitly said they do not need a separate demo page: use the same app.
Do not build a separate public sandbox/page. The existing 1,351-record catalog and
sprites remain in use; no new snapshot/catalog relocation was needed. The old separate
demo stack was stopped; legacy fixture files remain as historical/offline tooling.

Current controls under /api/admin require active superuser sessions. POST /refresh
queues a full live Pokemon+18-type refresh. POST /demo/changes accepts up to six
Pokemon stat/type patches and twelve type matchup patches. Identical payload repeats
are idempotent; a different active scenario must be reset first. POST /demo/reset
restores only captured fields and removes only tagged demo history, refusing newer
conflicting source values. Accounts, teams, unrelated fields and normal history are
preserved. GET /jobs and /jobs/{id} expose queued/running/final status and final counts.
All writes return 202/Location and the API does not execute scans in-process.

Migration 0004_admin_jobs adds admin_jobs and singleton demo_state. The separate
Compose scanner now runs app.jobs.worker --schedule, polling the durable queue while
retaining scheduled full scans. A worker advisory lock serializes queue consumers;
the existing scan lock serializes actual writes with other CLI/live scans. Unfinished
running jobs become interrupted after restart. Manual changes carry source/manual_demo
and a scenario ID in ScanRun.summary; alert responses/UI label those events explicitly.
Reset is atomic and deletes only history associated with that scenario's tagged scans.

ENABLE_DEMO_CONTROLS defaults false in application settings; local compose.yaml
explicitly enables it by default for API and worker, configurable via .env. Do not
overwrite existing .env. The existing single owner account was granted is_superuser
for local review, with no new account/password changes. Registration cannot grant
admin access. CLI: python -m app.jobs.admin grant|revoke username. The frontend proxies
/docs and /openapi.json, so use http://localhost:8080/docs after logging into the normal
app. Direct :8000/docs also works using the existing localhost cookie. Cross-site
admin writes remain blocked; the API's own docs origin is allowed for admin routes.

Tests passed: 114 PostgreSQL, 99 SQLite (15 skips), 22 component, 4 ordinary Chromium
flows. The new admin browser test uses a real separate scanner-test worker, checking
queue/status, visible tagged alerts, repeat and reset. Old separate demo E2E remains
opt-in/skipped. Test containers/network removed. Reports: test-artifacts/admin-controls/.
Clean source build context: /tmp/pokemon-admin-controls. Detailed walkthrough:
agent-process/05-admin-scanner-controls.md. Development API/frontend/scanner refreshed,
Alembic check passed. A queued live-refresh job succeeded: all 1,351 Pokemon and all 18 type rows
unchanged, zero failures. Counts remain 1,351 Pokemon, 2 teams, 1 account and zero
catalog changes; migration head is 0004_admin_jobs. No fictional changes are active
in development. Same-app Swagger and OpenAPI paths were verified. Next remain public
hosting, one-page README, and the previously recorded pre-deployment cleanup tasks.


## Latest: compact workspace UX, profile and unread alerts

The owner requested less copy, aligned login/register cards, page-size selection,
multi-type/stat filters, header sign-out/profile controls and a closed alerts tray
with a red unread count. These are implemented using the existing palette. Page sizes
12/24/48/96; type any/all and inclusive min/max ranges for all six stats. Filters are
collapsed by default and reset offset when changed; the API retains legacy type=.
The builder stays mounted while Profile is open, preserving drafts. Profile can rename
the account, change its password, and view/edit/delete saved teams. Current password
verification is required; password changes revoke all sessions, including the current
one. Sign-out clears the #profile route. No privilege fields are accepted by PATCH
/api/profile, and account ownership stays on the same UUID.

Migration 0005_alert_reads adds user/change acknowledgements with cascading removal.
GET /api/alerts now includes unread_total and item.is_read. POST /api/alerts/read marks
only currently relevant IDs for the signed-in user, idempotently. The closed-by-default
native modal drawer marks its displayed page as read after acknowledgement; unviewed
pages remain unread. The badge persists across reload/login and counts only current
saved-membership/window matches. Refresh happens on saved-membership changes, focus,
a 60-second timer and explicit refresh. Failed acknowledgements keep the unread count.
Header controls are rendered in App's header through a portal; standalone component
tests use the same toolbar without the portal target.

Tests: 120 PostgreSQL, 105 SQLite (15 skips), 22 components, 5 regular Chromium flows.
Old isolated-demo E2E stays opt-in. Screenshots/reports: test-artifacts/workspace-ux/.
Clean build source: /tmp/pokemon-workspace-ux. Read agent-process/06-workspace-ux.md.
An old saved-copy assertion was updated; the new browser test caught and fixed stale
profile navigation after password-triggered sign-out.

Important deployment recovery: existing main app had 2 manual-demo history events
and an active demo_state. Restarting the old worker triggered a full live startup
scan, reversing two demo changes before cancellation. The worker was stopped. Only
those two interrupted-run values/events were transactionally restored/removed after
checking current values matched that run; the original 2 events and read state were
retained. The interrupted audit is marked deployment_rollback, and a succeeded
scope=restore/source=deployment_restore audit records recovery. The active scenario
was not reset. Do not treat this as permission to delete ordinary source history.

The worker now calculates the remaining interval from the last completed full live
scan on restart; manual demo/reset/recovery audits are ignored. Explicit admin refresh
continues to work independently. A regression test checks remaining/overdue timing.
This scheduling fix was followed by a full backend rerun. The corrected scanner image is running and verified: roughly 23 hours remain until
the next scheduled live scan, the active demo's edited fields still match its applied
values, and the original history count remains two. API/frontend run the new UX;
account and teams remain intact, migration head is 0005_alert_reads. Do not
force browser refresh or discard the owner's draft. Next remain public hosting and
final one-page README, plus recorded deployment-hardening follow-ups.

Final runtime verification passed health and metadata checks. The worker restart
permission review timed out once; the permitted retry succeeded. All services are
running, and no automatic startup scan modified the restored scenario. Final current
tests are 120 PostgreSQL, 105 SQLite with 15 skips, 22 component and 5 normal browser
flows. Commit/push this completed increment; do not reset the owner's current demo.


## Latest: sorting, sliders and selected-team comparison

The owner's follow-up requests are implemented: default Index sort plus low/high
ordering for all six base stats; paired native range sliders in place of number
boxes; shared type chips across filters, catalog and selected team; six stats always
visible per occupied team slot; selected cards outlined with an In team count.

GET /api/pokemon adds a validated sort enum (index or stat_asc/stat_desc). SQL sorting
precedes pagination with Pokemon.id ascending as the tie-breaker. Response.stat_maxima
uses the entire catalog independently of filters, each at least 255 and higher when
stored/manual stats exceed it. Sliders show values and clamp handles instead of
crossing; default endpoints omit bounds, and keyboard/pointer interaction is tested.
Sort changes reset offset. No database migration is needed. Shared components live
in frontend/src/PokemonDetails.tsx and StatRange.tsx. TypeBadge styles are identical
on the three surfaces; checkbox/outline conveys filter selection without recoloring
its chip. Stats reuse the same labels/order in cards and selected slots.

Tests passed: 127 PostgreSQL, 112 SQLite with 15 skips, 23 components and 6 regular
browser flows. A duplicate selected-count label was caught by screenshot review,
removed from team slots and covered by an exact card-only count assertion. Final
frontend checks reran after that correction. Build/test context is
/tmp/pokemon-catalog-compare; browser reports/screenshots are copied into
 test-artifacts/catalog-comparison/. Read agent-process/07-catalog-comparison.md.
Keep the scanner's restart-delay fix from the previous increment; do not allow a UI
refresh to overwrite an active manual scenario. Leave existing accounts, teams,
manual state and history intact. Deployment verification passed: all services healthy, no schema drift, live sorting
and global slider domains correct. Counts remain 1,351 Pokemon, 2 teams, 1 account,
2 change events and 1 active demo scenario. The worker respects its remaining delay
and did not launch a startup scan. This increment is committed as “Add stat sorting,
range sliders and selected-team comparisons”. Next remain hosting and final README.

## Latest: alerts presentation

Alerts now use title-case event headings, compact before/after chips and indented
Pokémon with shared type badges. Type-matchup events show attacking/defensive relevance;
saved team/slot references remain beneath each affected Pokémon. The alert API adds
current types to affected entries. No migration is required. Scanner and read semantics
are unchanged. See agent-process/08-alerts-presentation.md.

Verification passed: 127 PostgreSQL, 112 SQLite (15 skips), 24 component tests and six
regular Chromium flows. Desktop/mobile screenshots reviewed and retained locally in
test-artifacts/alerts-polish/. Development updated from tested images; preserve the
existing database and active manual scenario. Save drafts before refreshing the browser.
Runtime checks passed: all services healthy, no schema drift, and counts remain
1,351 Pokémon, two teams, one account, two history events and one active manual
scenario. The worker retained its remaining scheduled interval without a startup scan.

## Latest: cumulative demo and dated alert history

Manual demo requests now merge into one active scenario instead of rejecting a different
payload. Each field retains its first original value and latest demo value, sharing the
same demo ID across requests. Reset restores all tracked originals and removes all
scenario-tagged events. Current values that differ from the tracked demo value block
further edits to that field; reset also retains its newer-source safety check. No
migration required; existing snapshots work unchanged.

Alert responses add per-field history for the full configured window before pagination,
scoped to the same entity key and saved-team relevance. UI groups cards by local date
and offers View history for repeated field changes, newest first with detection times.
Read tracking still applies only to visible alert events. See
agent-process/09-cumulative-demo-history.md. Do not reset the owner's live scenario.
Final tests: 129 PostgreSQL, 113 SQLite (16 skips), 25 component and six regular browser
flows passed; production build passed. Reports: test-artifacts/alert-history/.
Local app updated from tested images. Health and Alembic checks passed, worker retained
its remaining scan interval, and counts before/after remained 1,351 Pokémon, two teams,
one account, one change event and one active demo scenario. These reflect the owner's
latest scenario, which was preserved. Save drafts before browser refresh. Commit this
increment as “Support cumulative demo changes and dated alert histories”.

## Latest: team pane actions

Draft a New Team is now the selectable blank entry in Saved teams; the separate New
team button is removed. Existing discard confirmation applies to dropdown switching.
The team pane is viewport-constrained with a keyboard-focusable member list that
scrolls independently and an action footer that remains visible. Counter preview and
Delete no longer require scrolling past all selected member cards. Stats/type chips
remain on every member. Member rows explicitly use max-content height to avoid stats
overlapping adjacent rows. Very short screens use a sticky footer fallback.
See agent-process/10-team-pane.md. No backend/schema/scanner changes are involved.
Verification passed production build, 25 components with one worker and six regular
Chromium flows (legacy separate-demo flow skipped). Row boundary and action viewport
assertions passed; screenshots reviewed. Reports: test-artifacts/team-pane/.
Only the local frontend is refreshed; backend/scanner/database remain running intact.
Commit: “Keep team actions visible and draft from team dropdown”.

## Latest clarification: expanded team list

The owner accepts a tall pane and wants actions accessible without going to its bottom.
The team list is expanded again, with no height cap/internal scrollbar; Save, counter
preview and Delete are above the members, directly after the name/draft status. The
Draft a New Team dropdown is retained. This supersedes the previous constrained-pane
layout. Only frontend changes; preserve the running backend and active demo.
The mobile team shortcut now focuses its heading and scrolls directly into position;
this fixes a resize/navigation failure exposed by the expanded pane. Build, 25 component
tests and six regular browser flows passed (legacy demo skipped). Mobile screenshot
reviewed; reports: test-artifacts/team-expanded/. Only frontend deployed successfully.
Commit: “Keep team members expanded with actions above the list”.

## Latest: restore bottom actions and fix desktop sticky positioning

Previous layout interpretations were superseded by the owner's clarification. Actions
are back below the full member list. The actual problem was position: sticky on a pane
taller than the viewport, which hid its bottom until the catalog container ended.
The pane now uses position: static at all widths, moving normally with page scrolling.
The dropdown drafting change remains. See the natural-scroll regression in teams.spec.ts.
Verified: scrolling 600 px reveals the bottom team actions while the catalog remains
far from its end. Build, 25 components and six browser flows passed (legacy demo
skipped). Screenshot reviewed; reports: test-artifacts/team-natural/. Only frontend
updated. Commit: “Restore bottom team actions and remove sticky pane positioning”.

## Latest: saved feedback in the button

A successful team save now turns the existing button green with Team saved. text,
instead of rendering a separate success message. Name/member edits clear that state
and restore the red Save team button. Unchanged saved state remains disabled. Delete
status and save errors remain separate. No backend/scanner changes.
Save-feedback verification passed build, 25 component tests and six regular browser
flows (legacy demo skipped). Reports: test-artifacts/save-button/. Only frontend updated.
Commit: “Show team save confirmation in the save button”.

## Latest: counter comparisons, paired-duel replay and Markdown guide

CounterPreview now uses the exact shared PokemonCard/Sprite/TypeBadges/StatList used
by the catalog. Your Pokémon is left, assigned counter right. The optimizer remains
safe-coverage-v1 with unchanged lexicographic exact assignment. New battle.py adds
paired-base-stats-v1 illustrative independent duels; response matchups contain simulation
inputs and bounded turn snapshots. The model uses base HP, a custom equal-power damage
formula, own-type effectiveness, better physical/special ratio, Speed order and
simultaneous ties. Immunity and 200-turn stalemates are explicit. It does NOT implement
official battle damage, learned moves, switching, abilities/items or win probabilities.

Run/next/result/restart controls reveal HP bars and auditable formulas/logs. A top
shortcut reaches simulation. Model/chart versions are available in the preview.
frontend/src/docs/counter-model.md is the single source for /counter-method, rendered
as safe React text with downloadable Markdown. README and app link to it. The guide
explains exact scoring, integer rounding, DP, candidate scope, all simulation rules,
examples, limits and reproducibility. No migration/dependency changes. Preserve existing
manual scenario, history and scanner restart-delay behavior during deployment.
Read agent-process/11-counter-comparison-and-replay.md.
Final verification: 134 PostgreSQL, 118 SQLite (16 skips), 27 components and six regular
browser flows passed; production build passed. Screenshots reviewed; reports at
test-artifacts/counter-replay/. Tested images deployed with healthy services and no
schema drift. Before/after counts remained 1,351 Pokémon, two teams, one account and
zero change events/active scenarios (the owner's current state). Scanner retained its
remaining interval. Commit: “Add shared counter cards, transparent duel replay and model guide”.

## Latest: duplicate counter IDs allowed

Owner requested counter-team duplicate rules match their own teams. Selection is now
safe-coverage-v2-duplicates: independently maximize each slot's (safe, type strength,
stats) tuple, lowest ID on ties. This exactly maximizes the additive team objective
without candidate exclusivity, in O(catalog size × n). Six identical opponents get six
copies of the same best counter. Removed insufficient-distinct-catalog rejection;
normal saved-team slot ordering preserves duplicates. Guide, README and UI updated.
Paired-base-stats-v1 simulation is unchanged; actual moves remain on hold. No migration.
Verified 135 PostgreSQL, 119 SQLite (16 skips), 27 components and six regular browser
flows; production build passed. Tested images deployed, health/schema checks passed.
Live six-Venusaur preview returned six copies of heatran-mega under the current catalog
and chart. Counts before/after stayed 1,351 Pokémon, three teams, one account, zero
change events and zero active scenarios. Worker retained its remaining scan interval.
Reports: test-artifacts/counter-duplicates/. Existing saved teams are not regenerated.
Commit: “Allow duplicate Pokemon in optimal counter teams”.

## Latest: app info and calculation/secret review

Added top-right App info icon, including signed-out pages. Native dialog lazily loads
public /api/info allowlisted metadata: release version from backend/pyproject.toml,
model versions, repo, catalog count, interval/window, latest full live refresh and
last successful full live refresh. Manual/sample scans excluded; errors/payloads and
all secret/user/session settings excluded. No-store response. Refresh info is GET only,
not a scan action; interval is not represented as a worker-health countdown.

Counter stat detail now substitutes actual inputs into R(a,b), durability and total
arithmetic. README includes real selection code and a tested worked score. Added exact
fraction rounding, bounds, monotonicity, permutation and HP-conservation checks. Test
coverage now 141 PostgreSQL, 125 SQLite (16 skips), 29 components, six regular Chromium
flows; production build passed. Reports: test-artifacts/info-audit/. Screenshots reviewed.

Secrets currently use ignored .env plus runtime Compose environment; not a managed
vault. Only .env.example tracked; no real values printed during review. Build contexts
now exclude .env variants recursively. Hosting still needs managed runtime secrets,
production credentials/secure cookies and access/rotation choices. No CI workflow yet.
No schema change. Read agent-process/12-app-info-and-calculation-audit.md. Preserve live
teams and scanner restart delay. Commit: “Add safe app info and strengthen calculation transparency”.
Runtime checks passed: all services healthy, no schema drift, public info allowlist
verified against live 1,351-entry catalog. Before/after counts stayed 1,351 Pokémon,
two teams, one account, zero events/scenarios. Worker retained its scan interval.

## Latest: simplified info and catalog source

Owner removed latest-attempt refresh metadata and model-version concepts. App info now
shows app release version, catalog source/count, interval/window, last successful live
refresh and repo/guide links. The source URL is the importer's CATALOG_URL constant,
https://pokeapi.co/api/v2/pokemon/?limit=200. No latest_live_refresh, counter_model or
simulation_model fields remain. Counter/replay model_version identifiers/constants and
version disclosures/history are removed from current code/API/UI/guide/README; actual
calculations and tests remain. App version and internal type-chart provenance remain.
Verified build, 141 PostgreSQL, 29 components and six Chromium flows (legacy demo skipped).
Source link/absent labels/contracts checked; desktop screenshot reviewed. Reports:
test-artifacts/info-cleanup/. Live API/frontend updated, no schema drift. Scanner kept
running without restart; no catalog/team/demo mutation was requested or performed.
Commit: “Simplify app info and link the catalog source”.
