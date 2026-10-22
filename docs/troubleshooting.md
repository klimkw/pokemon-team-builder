# Troubleshooting

Run commands from the repository root. Diagnose the failing layer before changing
configuration or data. Keep connection strings, cookies and passwords out of shared logs.

| Symptom | Check | Next action |
| --- | --- | --- |
| App does not open | `docker compose ps` and `docker compose logs frontend api db` | Confirm Docker is running, ports are available, and the API finished migrations. |
| Empty catalog | `docker compose logs daily-scanner scanner` | Run the one-shot scanner from the development guide. A skipped run means another writer owns the lock. |
| Changes do not appear locally | Whether the frontend is a Docker build or Vite dev server | Rebuild Docker services with `docker compose up --build -d`; only Vite provides source hot reload. |
| Login or mutations return 403 | Browser Origin versus APP_ORIGIN | Match scheme, host and port exactly. Use the same origin for the app and Swagger docs. |
| Login succeeds but session is absent | Cookie attributes in browser tools | Use Secure cookies for HTTPS; local plain HTTP requires COOKIE_SECURE=false. Check blocked cookies. |
| Session expires while editing | Recovery dialog and API status | Sign in through recovery to retain the in-memory draft. Reloading is not a draft recovery mechanism. |
| A team disappeared or changed | Whether another tab edited/deleted it | Retain the draft and save as a new team if needed. Updates currently use last-writer-wins semantics. |
| Demo operation returns 200 but has no effect | Response `status`, `error`, counts and catalog refresh | HTTP success is not proof the operation succeeded; a failed audit explains why. |
| Demo request returns 202 | `docker compose logs scanner` | Local worker mode needs the scanner worker. Hosted request mode completes in the request. |
| Normal user cannot inspect jobs | 403 from `/api/admin/jobs` | This is expected: job inspection and live-refresh endpoints require superuser access. |
| Hosted refresh returns 409 | Whether request mode is enabled | Use the GitHub Actions **Demo catalog scan** workflow for a live refresh. |
| Demo reset refuses newer data | Conflict message and latest scan | Do not force overwrite. Run a full live refresh and inspect the demo state before further changes. |
| Scan fails or partially succeeds | Failed IDs, scan audit and job logs | Correct the upstream/network/configuration issue and rerun; already committed records remain available. |
| Migration fails | `docker compose exec api alembic current` if API is running; startup logs otherwise | Fix the migration/configuration. Never drop tables, delete volumes or blindly stamp a revision. |
| Hosted DB TLS or lock errors | Direct/unpooled connection URL and certificate settings | Follow the deployment guide; scanner locks require session affinity. Do not disable TLS verification. |
| Tests touch the wrong environment | Compose file, project name and TEST_DATABASE_URL | Stop. Use the isolated test runner; never point destructive test cleanup at development/hosted data. |

## Inspecting failures

```bash
docker compose logs --tail=100 api scanner daily-scanner
docker compose ps
```

A healthy `/api/health` only proves the API process responds. Check database-backed
requests and App info's last successful refresh separately. Free hosted services can
sleep, and scheduled workflows can start late.

For automated failures, inspect `test-artifacts/` and the uploaded CI reports. SQLite
passes do not validate PostgreSQL locks; narrow Chromium screenshots do not validate
all mobile browsers. See [testing](testing.md) for the scope of each check.

For provider/import/plan failures, use the redacted workflow summary and
[infrastructure troubleshooting](../infra/terraform/README.md). Application rollback
does not reverse a database migration. Follow [deployment guidance](deployment.md)
and preserve recoverable data before making corrective changes.
