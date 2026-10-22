# Testing guide

This is the current guide to running and extending the suite. [archived testing notes](archive/testing-notes.md) retains
historical verification notes; old counts there describe earlier revisions.

## Run everything

Requirements: Docker with Compose v2 and Bash. From the repository root:

```bash
bash scripts/test.sh
```

The same command runs in `.github/workflows/tests.yml` on pull requests, pushes to
main/master, and manual dispatch. It builds the demo frontend (including
TypeScript checking), then runs SQLite tests, PostgreSQL tests with branch coverage,
frontend component tests with coverage, and Chromium browser tests. Test failures
are collected across layers and make the command fail. Build/setup failures stop
execution. The script always stops its disposable stack on exit.

The test stack uses its own `pokemon_test` database in tmpfs, its own Docker network,
and randomly allocated host ports. It does not load the development `.env` or remove
development volumes. To run alongside another test job:

```bash
TEST_COMPOSE_PROJECT=pokemon-team-builder-tests-local bash scripts/test.sh
```

Project names must start with `pokemon-team-builder-tests`. Reports are written to
`test-artifacts/`. Different simultaneous runs should use separate checkouts because
reports share that directory. CI uploads reports even when tests fail.

On hosts where Docker cannot read local dependency/cache folders, make a source-only
copy in a readable location, excluding `.env`, `.git`, `.venv`, `node_modules`, caches,
and generated artifacts; run the same script there. Copy its reports back afterward.

## What each layer protects

| Layer | Real dependencies | Purpose |
| --- | --- | --- |
| Pure backend tests | None beyond Python libraries | Scoring, tie-breaking, integer rounding, normalization, retry rules |
| Backend API/integration | FastAPI, SQLAlchemy, migrated SQLite or PostgreSQL | Ownership, validation, persistence, transaction rollback, alerts, jobs |
| PostgreSQL-only tests | Real PostgreSQL | JSONB, advisory locks, overlapping API writes, credential races, migration behavior |
| Frontend components | React in jsdom; controlled API responses | Draft retention, errors/retry, disabled actions, state transitions |
| Browser layout tests | Chromium; mocked API | Responsive editor visibility, keyboard focus, loading behavior |
| Full-stack browser tests | Chromium → Nginx → FastAPI → PostgreSQL; real worker | Authentication, recovery, team persistence, counters, profile, scanner alerts |

Browser layout mocks are explicit in `frontend/e2e/layout.spec.ts`; they are not
proof of backend integration. Session recovery tests use actual registration,
login, server-side logout/revocation, rejected login, reauthentication and saved
team retrieval. They run at desktop and mobile widths. They do not wait seven days
for natural token expiry; token expiry itself is tested by the backend.

The obsolete opt-in demo browser flow was retired. The regular admin browser test
covers real queued scanner changes, repeat/idempotence, alerts and reset, and cleans
up even after a failed assertion. Browser tests use synthetic catalog fixtures and
never depend on the live PokéAPI service. The test worker processes jobs without
starting periodic upstream scans.

## Focused runs

With Python 3.12 and uv:

```bash
cd backend
uv sync --locked
uv run --locked pytest -q
uv run --locked pytest tests/test_profile.py tests/test_worker.py -q
```

For PostgreSQL, use an explicitly disposable database named `pokemon_test`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://pokemon_test:disposable_test_password@localhost:55432/pokemon_test \
  uv run --locked pytest --postgres --cov=app --cov-branch --cov-report=term-missing
```

Tests create and remove a random schema per test. The test URL guard rejects the
normal development database. SQLite skips PostgreSQL-specific cases intentionally;
a SQLite-only pass is not the full backend result.

With Node 22.12+:

```bash
cd frontend
npm ci
npm test -- --maxWorkers=1
npm run test:coverage -- --maxWorkers=1
npm run build
```

One component-test worker avoids CPU contention from multiple jsdom instances.
This is separate from testing concurrent application requests.

For focused browser testing, start the standalone `compose.test.yaml` services,
seed `catalog-fixture`, and run the E2E service, for example:

```bash
docker compose -f compose.test.yaml up -d --wait db-test api-test frontend-test scanner-test
docker compose -f compose.test.yaml run --rm --no-deps catalog-fixture
docker compose -f compose.test.yaml run --rm --no-deps e2e npx playwright test session-recovery.spec.ts
docker compose -f compose.test.yaml down
```

Build the images first after source/dependency changes. The full-suite script handles
that automatically. Chromium is currently the only configured browser; a narrow
viewport checks responsive behavior, not Safari or a real mobile device.

## Coverage and test quality

Backend coverage includes branches and all `app` modules. Thread and greenlet
tracing are enabled for FastAPI and async SQLAlchemy. Frontend V8 coverage
includes application TS/TSX, excluding tests, test setup and declaration files.
Reports include unexecuted files; screenshots do not count as coverage or automated
visual comparisons.

Reports:

- `test-artifacts/backend/coverage.xml`, `coverage.json`, and `html/index.html`
- `test-artifacts/frontend/index.html`, `coverage-summary.json`, and `lcov.info`
- `test-artifacts/playwright-report/index.html` and failure traces/screenshots

Coverage is currently reported rather than gated by an arbitrary percentage. Review
uncovered branches for user/data impact. In particular, subprocess shutdown, real
network outages and high-load behavior need different checks than ordinary unit
coverage. A high percentage does not establish security or demo capacity.

Concurrency tests send overlapping HTTP requests while holding the target database
row, observe PostgreSQL lock waits, then release it. They assert coherent saved
lineups, deletion ordering and current-password revalidation. They avoid relying
on fixed sleeps to make requests overlap.

The alert-volume regression seeds retained read markers and many events and checks
that a page hydrates only its entities' history. It is a query-scope regression,
not a latency benchmark. Full per-field histories are still intentionally returned
for entities on the page, so unusually long histories can produce large responses.

When adding tests:

1. Name the user-visible rule or failure being prevented; keep related cases in
   feature-specific files.
2. Use units for arithmetic/boundaries, API tests for persistence/authorization,
   and a small browser flow for integration. Don't repeat every boundary in E2E.
3. Assert outcomes such as persisted IDs, preserved drafts or rejected access.
   Avoid CSS class names, exact fonts, incidental markup and exact pixel offsets.
4. Use controlled promises/events for asynchronous states and real database
   coordination for races. Do not hide failures with retries or fixed delays.
5. Isolate accounts and fixtures. Clean shared catalog mutations in `finally`.
6. Keep screenshots as diagnostics unless a deliberate visual baseline is added.

## Verification baseline — October 20, 2026

The testing-improvement run passed the demo build and TypeScript check,
172 PostgreSQL tests, 153 SQLite tests (19 PostgreSQL-only skips), 38 component
tests, and 15 Chromium scenarios (13 full-stack cases and 2 mocked browser-layout
cases). The final browser suite was rerun after fixing an ambiguous logout status
locator; no browser retries or skipped scenarios were used.

| Coverage source | Lines/statements | Branches |
| --- | ---: | ---: |
| Backend PostgreSQL suite | 89.83% | 80.45% |
| Frontend component suite | 94.14% | 85.51% |

These percentages do not include browser coverage. Backend uncovered paths are
concentrated in command-line wrappers and process/signal/error handling; frontend
coverage still has gaps in API error paths and less-used interactions. Coverage is
an aid to choosing the next meaningful test, not a demo-readiness claim.

The preserved local reports for this run are under
`test-artifacts/testing-quality/`; subsequent `scripts/test.sh` runs write to the
normal paths above. `full-suite.log` records the backend/component run and the
initial browser failure; `browser-final.log` records the passing browser rerun.
The isolated test containers and network were removed after validation. GitHub CI
has been added locally; its first hosted execution requires pushing these changes.

## Submission review — October 21, 2026

Validation of the submission changes passed:

- 166 SQLite tests; 23 PostgreSQL-only cases skipped intentionally.
- 189 PostgreSQL tests, including reviewer retirement and concurrent writes.
- 41 React component tests across 11 files, plus TypeScript and production builds.
- 13 Chromium scenarios: 11 full-stack journeys and 2 mocked layout cases.
- The final demo-image smoke suite and 18 Python infrastructure-runner tests.

Docker validation used a source-only copy under `/tmp` because Windows cache
permissions prevented direct build-context access. Initial runs exposed broken
architecture rendering with CRLF input and a browser assertion for a removed
counter explanation panel. Both were corrected. Two documentation tests timed out
under overlapping suite load; the final component run passed with one worker.
Final browser tests passed without retries. PostgreSQL coverage was 89.71% lines
and 80.65% branches. Reports and logs are preserved locally under
`test-artifacts/submission-review/` and are excluded from Git.

Read-only checks confirmed that the public frontend, architecture route and health
endpoint responded and that the catalog contained 1,351 entries. These checks
preceded the submission push; they do not establish deployment of the new commit
or a live authenticated end-to-end journey. Terraform provider build/configuration
checks were not rerun locally; the Python runner tests do not replace those checks.

## Demo container release check

Run `bash scripts/test-demo.sh` to build `Dockerfile.demo` and start it
against an empty, disposable PostgreSQL database. The image's normal startup command
runs Alembic before serving the built frontend and API. The smoke check covers built
assets and direct page links, catalog search, registration/login, secure cookie flags,
saved-team edits and persistence, counter preview, origin rejection and revoked sessions.
It is an HTTP packaging check; the separate Chromium suite covers browser behavior.

Demo cookie settings remain enabled. Because the isolated transport is plain
HTTP, the check explicitly replays the cookie after verifying Secure/HttpOnly/SameSite
attributes. It does not claim to test TLS termination, Neon TLS, live credentials or
Render itself. No demo secret is required, no live upstream request is made,
and demo controls stay disabled. Fixtures and smoke code are streamed into the test
container rather than added to the demo image.

CI runs this as the `demo-image` job alongside the application suite. Container
logs are saved under `test-artifacts/demo/` even on failure. The stack and tmpfs
database are removed on exit. Set `DEMO_TEST_PROJECT` to a unique name beginning
with `pokemon-team-builder-tests-demo` for simultaneous runs in separate checkouts.
