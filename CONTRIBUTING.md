# Contributing

Start with the [README](README.md), [development guide](docs/development.md) and
[architecture walkthrough](docs/architecture.md). Use the existing frontend/backend
packages; do not create a second root Python environment for the same service.

## Workflow

1. Inspect the working tree and preserve unrelated changes.
2. Keep changes focused on the requested behavior. Document important tradeoffs and
   add an [ADR](docs/adr/README.md) when changing an architectural boundary.
3. Install dependencies from committed lockfiles. Never commit `.env`, credentials,
   local databases, Terraform state/plans or generated test reports.
4. Add tests for changed behavior and meaningful failure cases. Use real PostgreSQL
   for locks, migrations and PostgreSQL-specific queries.
5. Run the relevant checks and summarize results, limitations and migration impact
   in the change description. See [testing](docs/testing.md) for full and focused runs.

## Data and access

Derive ownership from the authenticated user. Keep multi-row changes transactional,
use Alembic for schema/data changes, and preserve existing accounts and saved teams.
Tests must use isolated databases; never delete development volumes as a cleanup step.
Demo mutations affect the shared catalog when enabled, so use disposable fixtures for tests.

## Documentation

Keep the root README scannable. Put setup in `docs/development.md`, operations in
`docs/deployment.md`, failures in `docs/troubleshooting.md`, and rationale in
`docs/architecture.md` or ADRs. App-rendered guides import directly from `docs/`;
update the canonical file rather than making a frontend copy. Historical material
belongs in `docs/archive/` and must not be presented as current verification.

## Release validation

The application suite and deployment-image smoke check run in CI. Passing them does
not establish hosted credentials, external availability or production capacity.
Review [deployment](docs/deployment.md) before releasing migrations or infrastructure
changes; application rollback does not restore an old database schema.
