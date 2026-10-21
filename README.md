# Pokémon Team Builder

[Open the deployed app](https://pokemon-team-builder-f4w6.onrender.com/). Register a
username and password; no shared credentials are needed. Render's free service may
need a moment to wake after inactivity.

Search and filter the catalog, save an ordered team, generate an explained counter
lineup, and run its deterministic simulation. Saved teams persist across sessions;
recent source changes surface as alerts for affected teams.

## Run locally

With Docker installed, copy `.env.example` to `.env`, choose a database password, then:

```bash
docker compose up --build
```

Open http://localhost:8080. For a fresh database, populate the catalog separately:

```bash
docker compose run --rm scanner python -m app.jobs.scanner
```

Local Compose keeps its own database and scanner. It needs no demo credentials.

## Verify

```bash
bash scripts/test.sh
bash scripts/test-demo.sh
```

The first command runs backend tests against SQLite and PostgreSQL, frontend tests,
and Chromium user journeys in an isolated stack. The second builds the exact Render
Dockerfile, runs startup migrations on an empty PostgreSQL database, and checks
frontend assets, catalog queries, authentication, team persistence, counter generation,
origin enforcement and session revocation. Both clean up their disposable containers.
The demo smoke check uses synthetic catalog data and no demo secrets.
CI runs both checks on pull requests and deployment-branch pushes.

## Architecture and decisions

Read the [full architecture walkthrough](frontend/src/docs/architecture.md) for a
subsystem tour, rationale, assumptions, diagrams, tradeoffs and prioritized backlog.
The same document is available in the app under **App info → Architecture walkthrough**
at `/architecture`, with Markdown and diagram downloads.

- React/TypeScript frontend and FastAPI backend share one origin. Demo serves
  the built frontend from the API container; local Compose uses Nginx.
- PostgreSQL stores accounts, opaque sessions, owned teams, catalog and scan history.
  Alembic manages schema changes. Team writes are atomic; ownership is checked on
  every private operation and concurrent updates lock the team row.
- Counter generation ranks candidates for each opponent slot, explains the scoring,
  and simulates deterministic duels. Previewing never changes saved teams.
- A separate daily GitHub Actions scan refreshes PokéAPI data. Bounded retries,
  per-record transactions and an advisory lock handle failures and overlapping runs.
- Terraform adopts the existing Render and Neon resources with deletion protection.
  Render's configured deployment trigger waits for CI checks to pass; an existing
  service needs the Terraform plan/apply procedure to activate that change.

See [the project guide](PROJECT_GUIDE.md) for API contracts and implementation details,
[the testing guide](TESTING_GUIDE.md) for reports and test conventions, and
[deployment instructions](DEPLOYMENT.md) for secrets, scheduling and release operations.
The [infrastructure guide](infra/terraform/README.md) documents the pinned, tested
Render provider compatibility patch and its removal criteria.

## Scope and operational limits

This is a single-instance take-home deployment. Free hosting can sleep and scheduled
jobs can be delayed. Login rate limiting, account recovery, expired-session cleanup,
automated restore drills, database readiness and proactive freshness alerts remain
follow-up work. The current health endpoint checks process liveness. Deployment does
not automatically run authenticated tests against live user data.

Keep migrations compatible with the prior application release. Render rollback does
not undo schema changes; preserve Neon recovery history before risky changes. The
private repository's current GitHub plan does not enforce protected branches; the
Render CI gate controls automatic deployment, not pushes or manual deploys.

Signed-in reviewers may apply/reset shared catalog demo changes through `/docs`.
These affect every user; full catalog refresh and job history remain superuser-only.
Hosted demos run within a bounded request; daily real-source scans run in Actions.
See the deployment guide for the existing-settings rename checklist and temporary
legacy names used to preserve access to secrets and Terraform state.
