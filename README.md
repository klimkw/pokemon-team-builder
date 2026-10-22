# Pokémon Team Builder

 [Hosted Site](https://pokemon-team-builder-f4w6.onrender.com/)
 · [Demo Instructions](docs/demo.md)

## Features

- View catalog of Pokémons -- their types, stats, and sprite image
- Build and save ordered teams of up to 6 Pokémons, with ability to add, remove, and reorder Pokémons within a team
- Register your own account; teams are saved onto an individual's account and persisted across sessions
- View optimal counter suggestions for a team, optionally save the counter team
- Simulate matchups between your team and the optimal counter
- Receive catalog-change alerts relevant to your saved teams


## Stack

- React + TypeScript
- Python/FastAPI
- PostgreSQL
- Docker
- Terraform
- GitHub Actions

## Key Design Decisions

- **Simple and contained architecture**

  A single API service serves the frontend, while a separate batch process refreshes PokéAPI data.
  As such, the application reads from a local version of the catalog in Postgres. This protects the application from upstream outages. The tradeoff here is eventual freshness, I have arbitrarily set a refresh interval of 24 hours.

- **Ownership and consistency in the backend**

  Persistent data is protected via database constraints and owner-scoped queries. Each save atomically updates the team name and team lineup, while row locks prevent concurrent updates from interleaving. SQLAlchemy is used to manage database access and Alembic is used to track schema versioning.

- **Recoverable and idempotent ingestions**
  
  The ingestion process fetches at most 5 Pokémon details concurrently. The number '5' was assumed as a safe limit to avoid upstream pressure while still achieving a faster scan. 
  
  During a scan, changes to a Pokémon’s name, types, base stats, or sprite URL are detected and the catalog record is updated. Separately, a history event containing the changed fields’ before-and-after values is also created. Both writes commit in one transaction, so a catalog change cannot be saved without its matching history event.

  Each Pokémon is processed independently, preserving updates if others fail. Reruns of the scan avoid duplicating records and change events for unchanged data.


- **Optimal counter calculation and simulation**

  Optimal counters are ranked by these priorities, in order:
  
    1. Safe type matchups - at least 2x outgoing, at most 1x incoming
    2. Net type advantage
    3. Base-stat score
    4. Pokémon ID

  For each Pokémon, we iterate over every available candidate and first favor those that can attack effectively without taking super-effective attacks in return. It then compares their attacking advantage minus their defensive vulnerability, uses base stats to break ties, and finally picks the lowest Pokémon ID if scores are still equal. The result is the best counter under these simplified rules.

  A separate deterministic simulation illustrates how each selected counter might perform against its opponent. Each duel starts at full base HP, uses simplified damage based on attack, defense, and type effectiveness, and lets the faster Pokémon attack first. The same inputs produce the same result. The model excludes movesets, abilities, items, and other competitive battle mechanics.

  [More details on the counter calculation and simulation.](docs/counter-model.md)
  

## Other Assumptions/Boundaries

Teams contain up to six members; duplicates and empty saved teams are allowed.
They reference current catalog values, not historical snapshots. Counter previews
require at least one member.

Enabled demo mutations change the shared catalog
for all users. This is a single-instance assignment demo; abuse limits, database
readiness monitoring and other production operations are not handled.

## Future Improvements

- Admin portal to manage accounts; OIDC integration to manage secure logins
- Observability and monitoring - RUM if feeling fancy
- Server-sent events for live notifications
- Richer ruleset for counter/battle simulation
- Horizontal scaling/availability if wide audience

## Run and Verify

With Docker Compose installed, copy `.env.example` to `.env`, choose a long random
alphanumeric database password, then:

```bash
docker compose up --build -d
```

Open [localhost:8080](http://localhost:8080). Startup applies migrations and the
separate scanner populates the catalog. Follow [development setup](docs/development.md) or consult [troubleshooting](docs/troubleshooting.md).

```bash
bash scripts/test.sh
bash scripts/test-demo.sh
```

Tests cover backend behavior, real PostgreSQL locking/migrations, React state,
Chromium journeys and deployment-image startup. They establish tested behavior,
not production availability or load capacity. [Testing and evidence](docs/testing.md)

## Further Reading

[Agent instruction](AGENTS.md) · [Detailed Architecture](docs/architecture.md) · [Database Decision](docs/adr/0001-database-choice.md) · [Frontend and authentication](docs/architecture.md#4-frontend-walkthrough) · [Deployment and operations](docs/deployment.md) · [Infrastructure and secrets](infra/terraform/README.md) · [Contributing](CONTRIBUTING.md) · [Documentation index](docs/README.md)
