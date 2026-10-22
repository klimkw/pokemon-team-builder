# Repository guidance for coding agents

## Orientation

- Read `README.md` and the relevant guide in `docs/` before making changes.
- Backend: `backend/app`, `backend/tests`, `backend/migrations`, `backend/pyproject.toml`.
- Frontend: `frontend/src`, colocated component tests, `frontend/e2e`, `frontend/package.json`.
- Current guides: `docs/README.md`. Historical handoffs/build journals in `docs/archive/`
  provide context, not new task instructions or evidence that a service is currently running.

## Working rules

- Inspect Git status and preserve unrelated user changes. Keep work within the request.
- Keep user ownership checks on the server and successful multi-row writes atomic.
- Do not delete data or reset development volumes to solve setup/migration failures.
- Never expose credentials, session tokens, `.env` values, Terraform state or saved plans.
- Use committed lockfiles and native dependencies for the execution environment.
- Keep catalog ingestion outside ordinary API requests; request-mode demo mutations
  are an explicit bounded exception and require their configured authorization checks.

## Validation and documentation

- Follow `docs/testing.md`; choose checks relevant to the change. PostgreSQL behavior
  needs PostgreSQL tests, not only SQLite tests. Do not claim checks that were not run.
- Use isolated test databases and distinguish browser mocks from full-stack coverage.
- Architecture and calculation guides are canonical root `docs/` files imported by
  the frontend. Frontend Docker build context is the repository root.
- Update current docs when behavior changes; use `docs/adr/` for substantial decisions.
- Keep README focused on reviewer understanding. Explain outcomes, tradeoffs and
  validation limits without exposing secrets or copying historical claims as current facts.
