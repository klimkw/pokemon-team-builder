# Testing the application

Tests run alongside each feature. The test stack is separate from development:
`compose.test.yaml` uses project `pokemon-team-builder-tests`, database `pokemon_test`,
fixed disposable test credentials, its own network, and PostgreSQL storage in tmpfs.
It does not reference the development database password or mount its volume.
Do not merge the test file with `compose.yaml` using multiple `-f` arguments.

## Recommended: everything through Docker

Install Docker Desktop with its WSL 2 backend and Linux containers. Docker commands
can run from PowerShell; moving this checkout into WSL is not required. After any
required Windows restart, start Docker Desktop and check:

```powershell
docker version
docker compose version
```

Run these commands from the project directory (the folder containing compose.test.yaml).
The first run downloads/builds images, including the Playwright browser image.

```powershell
docker compose -p pokemon-team-builder-tests -f compose.test.yaml build
docker compose -p pokemon-team-builder-tests -f compose.test.yaml up -d --wait db-test api-test frontend-test
docker compose -p pokemon-team-builder-tests -f compose.test.yaml run --rm backend-tests
docker compose -p pokemon-team-builder-tests -f compose.test.yaml run --rm frontend-tests
docker compose -p pokemon-team-builder-tests -f compose.test.yaml run --rm e2e
docker compose -p pokemon-team-builder-tests -f compose.test.yaml down
```

Run cleanup even if a test command fails. `down` targets this test project only;
its PostgreSQL data is disposable, and bind-mounted reports are retained. Development
containers and the `postgres_data` volume belong to a different project.

On Windows, `powershell -File .\scripts\test.ps1` performs this sequence, stops at
the first failure, propagates failure, and attempts cleanup in a finally block.
It fixes the project name to `pokemon-team-builder-tests`. Use the individual Docker
commands above if your shell configuration does not allow local PowerShell scripts.

No host Python, Node.js, browser installation, or .env is needed for these container
tests. Test ports 55432 (PostgreSQL) and 18080 (frontend) are bound to loopback and
must be free. The internal browser visits http://frontend-test; the API accepts that
origin. The published frontend port is for connectivity inspection, not the default
browser login origin. See the local-browser override below if you want to use it.

## What PostgreSQL integration testing does

`backend/tests/conftest.py` accepts the explicit `--postgres` flag and reads only
TEST_DATABASE_URL for the test database. It refuses any database name other than
`pokemon_test` or a driver other than `postgresql+asyncpg`.

For each test requiring storage, the fixture:

1. Creates a random schema named test_<32 hex characters>.
2. Sets each connection's search_path to that schema.
3. Applies real Alembic migrations, then uses the real FastAPI app and SQLAlchemy adapter.
4. Drops only that exact generated schema in teardown, including after test failures.

Tests never truncate the public schema or delete a development database. Backend
integration tests and E2E may share the disposable database: E2E uses its public
schema, while integration tests use individually isolated schemas. Test-only engines
use NullPool because TestClient and asyncio.run helpers use different event loops;
asyncpg connections must not be reused across those loops. Production pooling is unchanged.

The complete existing backend suite runs on PostgreSQL, including account/session
handling, team ownership and rollback, catalog filters, ingestion, and migrations.
Two additional tests verify actual JSONB column types and PostgreSQL row locking:
a second connection cannot acquire a held team lock and succeeds after it is released.
PokéAPI HTTP responses remain mocked; these tests need no live upstream service.

## What the account E2E test does

`frontend/e2e/account.spec.ts` uses Chromium, a fresh browser context, and a unique
disposable username. No API routes are mocked. It exercises the built React UI,
proxy, real FastAPI Users endpoints, and PostgreSQL:

1. Register through the form; verify it returns to login and clears the password.
2. Submit a wrong password; verify the error and a 401 from /me.
3. Log in correctly; verify the account view and HttpOnly/SameSite cookie attributes.
4. Reload; verify the session survives.
5. Verify a separate browser context is unauthenticated.
6. Log out; verify the UI, cleared cookie, and unauthenticated /me.
7. Replay the old cookie; verify server-side session revocation.
8. Log in again to prove the account persisted, then log out.

Assertions wait for visible UI states rather than fixed sleeps. The test saves a
successful signed-in screenshot. Failures retain a screenshot and Playwright trace.
Traces contain test-only credentials/cookies; they are ignored by Git.

Reports appear under `test-artifacts/playwright-report`; screenshots/traces appear
under `test-artifacts/test-results`. With Node installed, view the HTML report:

```powershell
cd frontend
npm ci
npx playwright show-report ../test-artifacts/playwright-report
```

Playwright is pinned to 1.64.0 in package.json/lockfile and Dockerfile.e2e; keep both
versions aligned because the image supplies the matching browser binaries.

## Fast checks without Docker

```powershell
# From backend, with uv installed (Python 3.12):
uv sync --locked
uv run --locked python -m pytest -q

# From frontend, using Node 22.12+ (Node 24 recommended):
npm ci
npm test
npm run build
```

The default backend suite uses temporary SQLite databases: 112 tests pass, with
15 PostgreSQL-only tests skipped. It is a fast check, not a PostgreSQL substitute.
The frontend has 23 component tests using mocked HTTP responses. Vitest discovers
only src/**/*.test files; Playwright discovers e2e files separately.

## Run PostgreSQL tests or Playwright from the host

For PostgreSQL integration tests, start only the test database:

```powershell
docker compose -p pokemon-team-builder-tests -f compose.test.yaml up -d --wait db-test
# From backend after uv sync --locked:
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://pokemon_test:disposable_test_password@127.0.0.1:55432/pokemon_test'
uv run --locked python -m pytest --postgres -q
```

For host Playwright debugging against the test Compose stack, set the frontend origin
before starting/recreating the API, then run the test from frontend:

```powershell
# From the project root:
$env:TEST_APP_ORIGIN = 'http://127.0.0.1:18080'
docker compose -p pokemon-team-builder-tests -f compose.test.yaml up --build -d --wait db-test api-test frontend-test

# From frontend:
npm ci
npx playwright install chromium
$env:E2E_BASE_URL = 'http://127.0.0.1:18080'
npm run test:e2e
```

The origin override is for host-browser runs. Remove TEST_APP_ORIGIN from your shell
before using the default container E2E runner, whose browser origin is http://frontend-test.
No E2E data-reset endpoint exists; unique test accounts remain until the disposable
database container is stopped. The container runner seeds its small deterministic catalog automatically.

## Verification in this workspace

- PostgreSQL 17.11: all 51 backend tests passed, including migrations, JSONB and locks.
- SQLite: 49 passed, two PostgreSQL-specific tests skipped.
- React: 13 component tests passed; TypeScript check and production build passed.
- Chromium: the account E2E test passed against the real PostgreSQL-backed API and
  production React build, served through Vite's preview proxy on isolated test ports.
- Docker verification completed October 19, 2026: all 51 PostgreSQL backend tests,
  13 component tests, and both Chromium E2E tests passed using the isolated Compose
  stack and Nginx.
  All service health checks passed, and the test containers/network were removed.
- Building directly from the Windows-mounted checkout failed because Docker could not
  read metadata for backend/.pytest_cache, despite its .dockerignore exclusion. A
  temporary source copy under /tmp, excluding host caches and environments, built
  successfully. No application or permission changes were required. Dependencies
  remained installed inside the images; development data was untouched.
- Existing report files were not writable, so this run was saved under
  test-artifacts/docker-verification-20261019/.


## Team editor tests

`frontend-tests` runs Vitest inside the frontend build stage, which also checks
TypeScript and the production build. Six team-editor component tests cover the
six-member limit with duplicates, whole-team request order, failed-save draft
retention, discard cancellation, delete confirmation, empty teams, duplicate-submit
prevention, search/type query parameters, and visibility of all six stats.

`catalog-fixture` runs before container E2E and seeds 25 deterministic test records
into the disposable database's public schema, after API migrations. Its database
name/driver guard refuses anything other than PostgreSQL `pokemon_test`. Fixture
stats/types are intentionally synthetic and sprite URLs are null; the browser test
needs no live PokéAPI or image host. This service exists only in compose.test.yaml.

`frontend/e2e/teams.spec.ts` uses a separate unique account, real HTTP and database
calls, and the production UI. It verifies pagination, search/type filtering,
duplicates, capacity, explicit saves, reload persistence, rename/reorder/remove,
sign-out/sign-in persistence, multiple teams including empty ones, cancelled draft
discard, deletion, and mobile jump navigation without horizontal overflow. Desktop
and mobile screenshots are saved alongside the account screenshot. Tests use only
the disposable database and never populate the development catalog.

Latest UI reports/screenshots are retained under test-artifacts/team-builder-ui/.


Dependency follow-up: npm audit during this increment reported three findings in
existing development-only Vitest tooling (Vitest, @vitest/mocker, and tinypool;
one moderate and two critical package entries). The suggested fix is a major
Vitest upgrade. These dependencies are not copied into the final Nginx image;
resolve them in a separate tooling increment and rerun the component suite.


## Counter-team verification

The PostgreSQL suite now has 69 passing tests. Counter tests verify exact assignment
against exhaustive permutations on seeded small catalogs, greedy traps, priority order,
deterministic ties, distinct generated IDs, repeated opposing slots, type immunity,
dual-type multiplication, strongest return attacks, relative stats, and zero stats.
API tests verify validation, insufficient catalog handling, authentication/origin
checks, no-store responses, deterministic output, and zero preview writes.

The frontend suite now has 18 passing tests. Preview tests cover both directions of
effectiveness, assumptions/stat explanations, risky fallbacks, generation retry and
abort, failed-save name retention, separate-team saving, and duplicate-save protection.
jsdom supplies minimal dialog methods; real modal behavior is tested in Chromium.

There are three E2E tests. The counter flow adds an unsaved member to a saved source,
previews the current draft, reads the method/stat explanations, verifies mobile modal
width, saves a separate counter, verifies the source draft and saved source are
unchanged, dismisses a second preview with Escape, and reloads the saved counter.
Screenshots/reports are retained under test-artifacts/counter-teams/.


A read-only development smoke check generated six distinct counters against all
1,351 imported records in approximately 0.35 seconds in this Docker environment.
The six selected matchups were safe under the model. This is a measured sample,
not a latency guarantee. Development catalog/team/account counts were unchanged;
no temporary development accounts or teams were created for this check.


## Scanner/history verification

The current backend suite has 93 PostgreSQL tests. New checks cover baseline imports
without change entries, field-level Pokémon diffs, idempotent repeats, atomic rollback
when history insertion fails (both Pokémon and type chart), incomplete/conflicting type
rows, and counter previews observing the database chart without restart. PostgreSQL-only
checks exercise full scans, mixed failures, failed discovery, overlapping real advisory
locks, shutdown cancellation, abandoned-run recovery, and refusing writes after loss of
the lock connection. Scheduler tests use a short interval and events instead of waiting
hours. Both environment settings are checked for defaults, overrides, and invalid values.

The existing browser regressions exercise the migration and database-backed chart with
the full API. No scanner automatically starts inside the test API or test Compose stack;
tests call the scanner with controlled upstream data. No live upstream or development
DB is used by these tests. Development scanner activation is verified separately with
its normal full PokéAPI scan. Alerts and the dedicated user-facing demo are not built yet.

The final fast SQLite check passed 84 tests with 9 PostgreSQL-only skips.

The first live development service run succeeded with 1,351 unchanged Pokémon,
18 unchanged type rows, zero failures, and no new change events. Existing accounts
and teams were preserved. This verifies the normal separate-service startup; controlled
upstream-change tests remain isolated from development data.


## uv environment verification

Backend dependencies are declared in pyproject.toml and resolved in the committed
uv.lock. Docker uses pinned uv 0.13.3 to create an image-local .venv with locked sync;
the runtime omits the dev group and the test image includes it. Migration to uv
preserved all 43 previously installed package versions in the lock. uv lock --check
verifies metadata consistency; image inspection checks actual installed versions,
interpreter location, and runtime exclusion of pytest/aiosqlite. See the detailed
workflow in agent-process/03-python-with-uv.md.

The uv-built images passed 93 PostgreSQL tests, 84 SQLite tests with 9 skips, and all
3 Chromium regressions. Actual installed versions matched all 43 baseline packages,
and runtime inspection/offline lock checks passed.


## Backend structure refactor verification

The reorganized API, database, services, jobs, and shared schemas passed 93 PostgreSQL
tests, 84 SQLite tests (nine PostgreSQL-only skips), 18 frontend component tests, and
all three Chromium flows. The clean Docker build context contained only the new
module locations, so old source files could not mask missing imports. Test containers
and their network were removed after verification. Browser reports are retained in
`test-artifacts/backend-refactor/`.

Alembic metadata imports now use app.db.session and app.db.models. Historical revision
files are unchanged; development startup still applies migrations before serving HTTP.
The original app.ingest/app.scanner CLI wrappers preserve their exit codes and were
smoke-checked with --help. Compose uses the canonical app.jobs.scanner entry point.


## Alerts and deterministic demo verification

The current suite passes 106 PostgreSQL tests, 96 SQLite tests with 10 PostgreSQL-only
skips, and 22 component tests. Three normal Chromium flows pass; the separate demo
flow is skipped in that stack and run explicitly against compose.demo.yaml instead.
The added backend tests cover authentication, no-store headers, ownership, grouped
slots, configurable window/exact cutoff/future exclusion, attack and defense type
relevance, current saved membership, pagination, and scan status without raw errors.

The real PostgreSQL demo test invokes the scanner with a fixture HTTP transport and
checks baseline/change/repeat: zero, two, then still two history entries and alerts.
The CLI separately refuses non-demo database targets or a missing DEMO_MODE flag.
The standalone Docker stack also ran each stage successfully without live upstream
requests. Its dedicated Chromium flow checks visible before/after values, grouped
slots, saved versus unsaved membership, attacking-type relevance after a save, and
mobile width. A first browser selector matched the sign-in tab and submit button;
it was narrowed to the form submit button, then the test passed.

Normal browser reports: test-artifacts/alerts/.
Demo screenshots and browser report: test-artifacts/alerts-demo/.
The demo uses its own cookie name, database, network, and ports 8081/8001. Its
fictional changes are visibly labelled. See agent-process/04-alerts-and-demo.md for
manual steps, expected results, and resetting only the disposable demo project.

To run just its browser test after change/repeat, build the e2e image with the normal
test Compose file, then run it on the demo network with E2E_DEMO=true and
E2E_BASE_URL=http://demo-frontend, selecting demo.spec.ts. For that container-browser
run only, start demo-api with DEMO_APP_ORIGIN=http://demo-frontend; restore the default
http://localhost:8081 origin afterward for manual browser use. No development origin
or database settings need to change.

Development refresh passed health and Alembic metadata checks, preserved all 1,351
Pokémon, two teams and one account, and the full scanner succeeded without new change
history. Manual demo-origin login confirmed its separate cookie and two no-store alerts.


## Same-app admin controls verification

Current results: 114 PostgreSQL tests, 99 SQLite tests with 15 PostgreSQL-only skips,
22 component tests, and four regular Chromium flows. The historical separate-demo
browser test remains skipped unless explicitly enabled. Added checks cover superuser
access, disabled demo controls, strict input validation, same-origin docs and cross-site
rejection, durable 202 responses, queue exclusivity, scanner-lock contention, safe
reset, unrelated field/history preservation, conflicting newer values, partial refresh,
shutdown cancellation and interrupted-job recovery. Migration upgrade/check/downgrade
round trips cover the new admin_jobs and demo_state tables.

The test Compose stack now includes a separate scanner-test worker with periodic live
scans disabled. Its DB remains disposable pokemon_test. The fixture seeds a test-only
superuser. The Chromium admin flow signs into the normal frontend, validates the docs
and OpenAPI routes, queues manual changes and polls the real worker, checks visible
labelled alerts, repeats without duplicate history and resets back to the original
stats. The fixture team is removed afterward. No live upstream service is needed.
All test containers and their network were removed. Reports/screenshots are under
`test-artifacts/admin-controls/`.

The running development stack uses the same tested images and Alembic check reports
no schema drift. Existing account/team/catalog data was preserved. The old separate
demo stack was stopped at the user's request; the same-app walkthrough is documented
in agent-process/05-admin-scanner-controls.md. Its owner account was explicitly granted
admin access, and a full-refresh job was queued for deployed-worker verification.

The deployed refresh job completed successfully with all 1,351 Pokémon and 18 type
rows unchanged and zero failures. Two teams, one account and zero existing change rows
were preserved; migration head is 0004_admin_jobs. No fictional data is active in the
main app. The owner can now perform the walkthrough through the same app's docs.


## Workspace UX, profile and unread-alert verification

Current results: 120 PostgreSQL tests, 105 SQLite tests (15 PostgreSQL-only skips),
22 component tests, and five normal Chromium flows. The older isolated-demo flow
remains opt-in. TypeScript and production builds passed. Backend checks cover combined
multi-type filters, any/all matching, stat bounds, profile verification/rename/conflict,
password revocation and per-user persistent alert acknowledgements. Component tests
verify the initially closed tray, unread count/read failures, filtering and draft safety.

The added browser flow measures identical login/register card dimensions, verifies
header controls and page size, exercises type/stat filters, preserves a draft across
Profile, edits credentials, signs back in with the new password and deletes a team.
Mobile profile width is checked at 390px. The admin flow verifies a real red unread
badge before opening the tray, its removal after acknowledgement and persistence on
reload, with the normal separate worker performing the underlying changes.

The shortened Saved label required updating an old copy assertion. A browser test
caught stale profile navigation after password-triggered sign-out; sign-out now clears
the route. All final browser flows passed. Screenshots/reports:
`test-artifacts/workspace-ux/`.

During deployment, an automatic scanner startup began reversing an active manual
scenario. It was stopped, its two changes were transactionally restored, and only the
history entries generated by that deployment scan were removed. Original demo history,
read state, account and teams were preserved. The worker now respects the remaining
scan interval across restarts, with a tested overdue/remaining-delay calculation. Full
backend checks were rerun after this scheduling fix; normal explicit refreshes remain
available. See the process walkthrough for the recovery audit and semantics.

Final runtime check confirmed the corrected worker waits for its remaining interval,
all active manual fields match their applied values, and original history remains at
two events. Health and Alembic metadata checks passed. The running UI is updated; the
owner should save any draft before refreshing their browser.


## Catalog sorting, sliders and team comparison

Current checks passed 127 PostgreSQL tests, 112 SQLite tests with 15 PostgreSQL-only
skips, 23 component tests and six regular Chromium flows. All twelve stat ordering
choices are tested for numeric order, stable index ties, filter combination and
pagination. Invalid sorting is rejected; global slider maxima remain available for
empty filtered results and expand for unusually large catalog/demo values.

The range component exposes two labelled native handles, visible selected values and
clamping. Chromium checks both keyboard increments and a real pointer drag, then
clears filters. It checks selected-card counts, all six visible team stats, matching
computed type-badge colors/fonts across filters/cards/team members, and mobile width.
The existing workspace range-input check now exercises the slider with keyboard keys.

Visual review caught an extra selected-count label rendered in a team slot and
positioned over its panel. It was removed; a browser assertion now verifies that only
the catalog card has the count. Component and browser suites were rerun afterward.
Reports/screenshots: test-artifacts/catalog-comparison/. Test containers and their
network are cleaned up separately from development.

The local app was updated using the tested images. Live sort/domain queries and
Alembic check passed. Counts remain 1,351 catalog entries, two teams, one account,
two history entries and one active manual scenario. The scanner retained its remaining
interval and did not run a new startup refresh. No schema migration was required.

## Alerts presentation

Passed 127 PostgreSQL tests, 112 SQLite tests (15 PostgreSQL-only skips), 24 component
tests and six regular Chromium flows. The legacy separate-demo browser flow remains
opt-in/skipped. Production frontend build passed inside Docker. Checks cover current
affected Pokémon types, title-case headings, accessible before/after change chips,
shared type badges, defensive relevance, persisted unread handling and mobile width.
Desktop/mobile screenshots were visually reviewed; reports: test-artifacts/alerts-polish/.
The isolated test stack was removed after verification.

## Cumulative demo and field history

Integration checks cover successive requests updating the same stat and type pair,
adding another stat, repeat idempotence and resetting all four generated events back
to original values. Existing newer-source reset protection remains covered. A separate
history test checks stable entity identity, time-window filtering, descending timestamps
and entries beyond the current alert page. Component coverage checks collapsed history
and expansion. The regular admin browser flow now applies a second request, expands
Attack history, checks date grouping and mobile width, then repeats and resets.

Final verification passed: 129 PostgreSQL tests, 113 SQLite tests with 16 PostgreSQL-only
skips, 25 component tests and six regular Chromium flows. The legacy separate-demo
flow remains skipped. Production Docker build passed. Screenshot review confirmed
readable date headings and expanded timestamped history; mobile overflow passed.
The first build caught misplaced JSX closing tags, corrected before the full rerun.
Reports/screenshots: test-artifacts/alert-history/. Test containers were cleaned up.

## Team pane dropdown and visible actions

Production frontend build and 25 component tests passed. The catalog-loading component
wait timed out under parallel suite contention; the same tests passed with one Vitest
worker, without changing expectations. Browser checks select the new blank dropdown
entry, preserve unsaved edits on cancelled switching, and verify counter/delete actions
are in view on 390×844 mobile and 1440×720 desktop. Screenshot review caught compressed
member rows causing overlapping stats; max-content row sizing corrects this, with an
explicit row/stat boundary assertion added to the browser flow.
Final rerun passed all 25 component tests and six regular Chromium flows (legacy demo
flow skipped), including the new row boundaries. Desktop/mobile screenshots reviewed;
reports: test-artifacts/team-pane/. Isolated test containers were removed. Backend
suites were not rerun for this frontend-only change.

## Expanded member list clarification

The owner clarified that pane height may exceed the viewport. Removed the list height
cap/internal scrollbar and moved actions before the full member list. The mobile
shortcut now explicitly focuses/scrolls to its heading after a browser check exposed
an unstable jump during resizing. Production build, 25 components (one worker) and
six regular Chromium flows passed; legacy demo skipped. Action visibility, discard
protection and nonoverlapping stats still pass. Mobile screenshot reviewed; reports:
test-artifacts/team-expanded/. Only frontend refreshed; no backend tests were rerun.

## Natural team-pane page scrolling

Restored actions below the full member list and removed desktop sticky positioning.
The regression scrolls 600 px, checks the pane moved by more than 550 px, checks both
counter/delete actions are visible and proves the page end is still over 500 px away.
Screenshot review confirms all three actions below the list at that scroll position.
Production build, 25 components (one worker) and six regular Chromium flows passed;
legacy demo skipped. Reports: test-artifacts/team-natural/. Only frontend deployed.
