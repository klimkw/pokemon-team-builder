# Development

## Repository layout

```text
project/
├── README.md                 Reviewer overview and quick start
├── AGENTS.md                 Coding-agent guidance
├── CONTRIBUTING.md           Contributor workflow
├── .env.example              Local configuration template
├── backend/
│   ├── pyproject.toml        Python dependencies and tooling
│   ├── uv.lock               Locked Python dependencies
│   ├── app/                  API, services, database and jobs
│   ├── migrations/           Alembic schema and data migrations
│   └── tests/                Backend tests
├── frontend/
│   ├── package.json          JavaScript dependencies and scripts
│   ├── src/                  React components and component tests
│   └── e2e/                  Browser tests
├── docs/                     Current guides, ADRs and historical notes
├── infra/terraform/          Infrastructure configuration and provider notes
└── scripts/                  Test and infrastructure runners
```

Python metadata stays with the backend; the project has two distinct application
packages rather than a single root `src/`. Commands below run from the repository
root unless a different directory is specified.

## Run and test

Install Docker with Compose. Copy `.env.example` to `.env` and choose a long random
alphanumeric database password. Keep `.env` untracked.

```bash
docker compose up --build -d
docker compose logs -f api daily-scanner
```

Open [the app](http://localhost:8080) and [API docs](http://localhost:8080/docs).
The API applies migrations before startup. The separate daily scanner refreshes a
fresh catalog; explicitly request a scan with:

```bash
docker compose run --rm scanner python -m app.jobs.scanner
```

An overlapping run safely skips when another writer holds the database lock. The
`scanner` service consumes queued operations; `daily-scanner` schedules live scans.
Use `docker compose stop` to retain data. Do not remove the development database
volume to troubleshoot a migration.

```bash
bash scripts/test.sh
bash scripts/test-demo.sh
```

These use disposable environments, not the development database. See the
[testing guide](testing.md) for focused tests and report locations. After changing
source, `docker compose up --build -d` refreshes the local images.

## Backend without Docker

Use Python 3.12 and uv. Supply `DATABASE_URL` for your development PostgreSQL database
and set `APP_ORIGIN=http://127.0.0.1:5173` when using the Vite frontend. Local HTTP uses
`COOKIE_SECURE=false`; hosted HTTPS uses true. Export settings in the shell or editor;
the Python service does not automatically load the root `.env` file.

From `backend`:

```bash
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --reload
```

Keep long-running imports outside the API process. From the same environment, use
`uv run --locked python -m app.jobs.scanner` for a one-shot refresh. The scanner
requires PostgreSQL; SQLite is used only for portable test coverage.

## Frontend without Docker

Use Node 22.12 or later. From `frontend`:

```bash
npm ci
npm run dev
```

Vite serves at [127.0.0.1:5173](http://127.0.0.1:5173) and proxies `/api` to
`http://127.0.0.1:8000`. `API_PROXY_TARGET` overrides that target. Keep APP_ORIGIN
identical to the browser origin; `localhost` and `127.0.0.1` are different origins.
Use browser Network and Console panels to distinguish API failures from rendering errors.

The guide components import `../../docs/*.md?raw`. Docker builds therefore use
repository-root context:

```bash
docker build -f frontend/Dockerfile -t pokemon-frontend .
```

Do not reuse Windows `node_modules` or virtual environments inside Linux containers.
Use the lockfiles to install native dependencies for each environment.

## Changing the project

Keep routes responsible for HTTP validation and authorization, services responsible
for reusable logic, and jobs responsible for scheduled work. Never trust a client
supplied owner ID. Schema/data changes need an Alembic migration and tests against a
real PostgreSQL database when they depend on PostgreSQL behavior.

Update the relevant guide with behavior changes; record substantial decisions in
[docs/adr](adr/README.md). Review the [contribution guide](../CONTRIBUTING.md) and
[troubleshooting guide](troubleshooting.md) before changing infrastructure or data.
