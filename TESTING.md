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
# From backend, in a Python 3.12 virtual environment:
pip install -r requirements-dev.txt
python -m pytest -q

# From frontend, using Node 22.12+ (Node 24 recommended):
npm ci
npm test
npm run build
```

The default backend suite uses temporary SQLite databases: 49 tests pass, with the
two PostgreSQL-only tests skipped. It is a fast check, not a PostgreSQL substitute.
The frontend has 13 component tests using mocked HTTP responses. Vitest discovers
only src/**/*.test files; Playwright discovers e2e files separately.

## Run PostgreSQL tests or Playwright from the host

For PostgreSQL integration tests, start only the test database:

```powershell
docker compose -p pokemon-team-builder-tests -f compose.test.yaml up -d --wait db-test
# From backend with requirements-dev.txt installed:
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://pokemon_test:disposable_test_password@127.0.0.1:55432/pokemon_test'
python -m pytest --postgres -q
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
