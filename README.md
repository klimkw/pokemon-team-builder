# Pokémon Team Builder

[Hosted app](https://pokemon-team-builder-f4w6.onrender.com/) · [Demo walkthrough](docs/demo.md) · [Architecture](docs/architecture.md)

Build, name, reorder and save multiple teams of up to six Pokémon. Browse the
responsive catalog, generate an equal-size counter team, simulate its matchups,
and receive alerts about changes affecting your saved teams. Register a personal
account to keep teams across sessions.

## Design decisions

- **React + TypeScript, FastAPI and PostgreSQL.** A single API serves the hosted
  frontend; a separate batch job refreshes PokéAPI data. Reading a local catalog
  keeps browsing independent of upstream outages, at the cost of eventual freshness
  (a configurable 24-hour scan interval).
- **Ownership and atomic saves.** Server-side owner checks isolate accounts.
  Database constraints protect ordered membership, and each save updates the name
  and lineup in one transaction. Row locks prevent concurrent writes from
  interleaving; separate tabs still use last-write-wins semantics. SQLAlchemy handles
  persistence and Alembic versions the schema.
- **Recoverable ingestion and notifications.** Discovery follows every catalog
  page; detail fetches use bounded concurrency of five. Each changed record and its
  before/after history commit together. Successful records survive partial failures,
  and unchanged reruns create no duplicate events. A separate scanner also checks
  the 18-type effectiveness chart. Alerts show relevant changes from the last seven
  days; controlled demo mutations make this rare upstream behavior reproducible.
- **An explicit definition of optimal.** Counter selection maximizes safe matchups
  (at least 2× outgoing and at most 1× incoming), then net type advantage, then a
  relative base-stat score; lowest Pokémon ID breaks ties. With reusable candidates
  and independent slots, selecting each slot's best candidate exactly optimizes
  this objective. The deterministic battle replay illustrates the result using
  simplified damage and speed rules. [Scoring and simulation](docs/counter-model.md)

## Assumptions and tradeoffs

Order matters. Duplicate members and empty saved drafts are allowed; previews need
at least one member. Teams reference current catalog values, not snapshots. All
catalog forms are eligible; movesets, abilities, items and switching are outside
the counter model. Unsaved drafts live in browser memory.

Enabled demo mutations affect the shared catalog for every user. This is a
single-instance assignment demo. Production follow-ups include abuse limits,
database readiness/freshness monitoring, tested backup restoration, and optimistic
concurrency. Docker, GitHub Actions and Terraform support repeatable builds,
validation and infrastructure management.

## Run and verify

With Docker Compose installed, copy `.env.example` to `.env`, choose a long random
alphanumeric database password, and run:

```bash
docker compose up --build -d
```

Open [localhost:8080](http://localhost:8080). Startup applies migrations; the
separate scanner populates the catalog. [Development setup](docs/development.md)

```bash
bash scripts/test.sh
bash scripts/test-demo.sh
```

The isolated suites cover backend behavior, real PostgreSQL locks/migrations,
React components, Chromium journeys and demo-image startup. Browser layout mocks
are distinguished from full-stack tests. [Testing and evidence](docs/testing.md)

[Demo instructions](docs/demo.md) · [Documentation index](docs/README.md) · [Contributing](CONTRIBUTING.md)
