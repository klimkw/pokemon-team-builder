# ADR 0001 PostgreSQL with SQLAlchemy and Alembic

Status: Implemented. A retrospective record of the implemented design.

## Context

Accounts own ordered teams, team members reference a shared catalog, and catalog
changes need durable history. Concurrent requests must not leave partially replaced
lineups. Separate scanners must coordinate even when launched by different processes.
The application also stores compact nested type/stat payloads.

## Decision

Use PostgreSQL as the runtime database, SQLAlchemy 2 async sessions with asyncpg for
application persistence, and Alembic for versioned schema/data migrations. Use JSONB
for small catalog payloads and relational keys/constraints for ownership and ordering.

Team saves commit name and members together and lock the parent row for concurrent
updates. Scanners use session advisory locks on a dedicated physical connection.
Explicit relationship loading avoids hidden asynchronous queries during serialization.

## Alternatives

| Alternative | Assessment for this project |
| --- | --- |
| SQLite runtime | Convenient single-file setup, but would not provide the PostgreSQL advisory-lock coordination used by separate scanners. Retained for portable tests. |
| Document database | Flexible catalog documents, but team ownership, ordering and atomic relational updates are central requirements; would require a different transaction/model design. |
| Raw SQL everywhere | Precise control, but more repeated mapping and lifecycle code. SQLAlchemy still permits explicit locks and SQL where needed. |
| Automatic table creation | Useful for prototypes, but does not provide a reviewable evolution path for existing data. Alembic makes changes explicit. |

## Consequences

The database enforces references and position constraints; migrations make fresh setup
repeatable. PostgreSQL integration tests remain necessary because SQLite cannot prove
JSONB or lock behavior. JSONB keeps the model small but may need expression indexes or
normalized columns if measured query workloads grow.

A row lock serializes saves but does not detect stale client edits. Per-record scanner
transactions preserve progress but do not create an atomic catalog-wide snapshot.
Advisory locks require direct/session-affine connections, and migration rollout must
remain compatible with the application version being deployed.

## Implementation references

- [Models and constraints](../../backend/app/db/models.py)
- [Session lifecycle](../../backend/app/db/session.py)
- [Atomic team writes](../../backend/app/api/teams.py)
- [Scanner connection ownership](../../backend/app/jobs/scanner.py)
- [Alembic migrations](../../backend/migrations/versions)
- [PostgreSQL concurrency tests](../../backend/tests/test_concurrent_requests.py)
