# Demonstrating changes in the same app through API docs

The owner chose API-doc controls in the existing app instead of a separate demo page.
The existing full catalog, sprites, accounts and saved teams remain in use. No fixture
catalog import or alternate frontend is needed. The older three-record Docker scenario
is retained as historical/offline test tooling, not the recommended review flow.

## Open the controls

1. Sign in to http://localhost:8080 using your existing account.
2. Open http://localhost:8080/docs in the same browser. The session cookie is reused.
3. Expand **Admin operations**. Each write operation has **Try it out** and **Execute**.

Only an active superuser can use these operations. Ordinary registration never grants
admin access. To grant or revoke an existing account explicitly from the project root:

```powershell
docker compose exec api python -m app.jobs.admin grant your_username
docker compose exec api python -m app.jobs.admin revoke your_username
```

Replace `your_username` with your registered username. Local Compose enables the demo
controls with `ENABLE_DEMO_CONTROLS=true` in both the API and scanner worker. The
application setting defaults to false outside that local Compose configuration; set
it false for deployments where you do not want manual data changes. Admin-only live
refresh remains available independently. Do not make the public fixture login an admin.

The docs also work at http://localhost:8000/docs after logging in through the app, since
cookies for localhost are shared across ports. Admin writes accept the configured app
origin or the API's own origin; cross-site browser requests remain rejected.

## Apply controlled changes and inspect alerts

Choose a Pokémon that occurs in one of your **saved** teams. Find its ID in the catalog
API if needed. POST `/api/admin/demo/changes` accepts, for example:

```json
{
  "pokemon": [{"pokemon_id": 1, "stats": {"attack": 60}}],
  "type_matchups": [
    {"attacking_type": "fire", "defending_type": "grass", "multiplier": 1}
  ]
}
```

Change the ID and values to fit your team, and use a value different from its current
stat. You can patch up to six Pokémon's base stats or types and up to 12 type matchups.
This is a fictional scenario supplied by the admin, not a claimed real source change.
It changes the shared catalog, so all saved teams using the affected data see it.

The response is HTTP 202 and includes the job ID and a status URL in the Location
header. Use GET `/api/admin/jobs/{job_id}` to poll until succeeded, partial or failed.
GET `/api/admin/jobs` lists the last 25 operations. Queued/running represent current
progress; final results contain inserted/updated/unchanged/failed counts. These are
completion summaries, not a live per-record progress bar. A stopped worker leaves
queued work stored in PostgreSQL rather than losing it with the HTTP request.

Return to the app and choose **Refresh alerts**. Each manual event is marked
“Demo change · applied manually through the scanner.” Before/after values and affected
saved-team slots use the ordinary alert query. Refreshing alerts preserves your editor
draft. To reload the catalog/member stats themselves, save or discard your draft and
reload the app when ready.

Submit the **identical payload** again and poll its new job. The scanner reports no
additional updates, and history does not duplicate. A different scenario is rejected
by its job while one is active; reset the current one first. Invalid IDs fail without
altering catalog data. Even a failed partial scenario retains its original-field
snapshot so it can be reset safely.

## Reset versus full live refresh

POST `/api/admin/demo/reset` queues a reset. It restores only the fields recorded in
the active scenario and removes only history tied to that scenario's tagged scans.
Accounts, teams, memberships, unrelated fields and normal scan history remain intact.
Reset and its completion are audited. Submitting reset with no active scenario is a
successful no-op. If another scan supplied a newer value for a demo-owned field, reset
refuses to overwrite it rather than restoring an outdated value.

POST `/api/admin/refresh` queues a full live PokéAPI discovery and refresh of all
Pokémon and 18 type rows. It never clears/replaces accounts or teams or deletes absent
catalog records. Real differences commit with ordinary change history. For example,
if a live refresh reverses a fictional Attack change, the reversal is a new source
change event, not an erased demo. This is intentionally different from reset.
Network failures can produce a partial result; inspect counts and rerun as needed.
The complete catalog remains available during refresh; individual successful records
commit independently. The chart only changes after all 18 rows validate.

## Backend execution and safety boundaries

Migration 0004 adds `admin_jobs` and `demo_state`. The API validates requests and saves
a durable queued job, then returns immediately. It does not launch a background task
inside the API process. Local Compose's separate scanner now runs
`python -m app.jobs.worker --schedule`: it polls the queue and still performs periodic
full refreshes using `CATALOG_SCAN_INTERVAL_HOURS`. The original scanner CLI remains
available for one-shot or legacy scheduled commands.

Only one queued/running admin operation is accepted at a time. The worker owns a
PostgreSQL advisory lock for its queue, recovers unfinished running jobs as interrupted
after restart, and uses the existing scanner lock to serialize imports, demo writes,
resets and scheduled/live refreshes. Work waits in the queue when another scanner owns
that lock. Interrupted work is not silently replayed: inspect its result and resubmit.

Manual inputs are constructed from the current records, with only requested fields
changed. They pass through normal catalog/chart synchronization and history generation.
Before scanning, `demo_state` saves those fields' original and applied values. Each
resulting ScanRun records a scenario ID and source marker. Reset checks the current
values, restores the captured fields and deletes only that scenario's events in one
transaction. It also preserves the normal scan audit. One shared active scenario is
appropriate for an admin-led walkthrough; it is not per-visitor sandbox isolation.

The real browser test logs into the ordinary app, validates its docs/OpenAPI routes,
queues an operation, waits for the separate worker, reads real alerts, repeats the
same input and resets. PostgreSQL tests cover privilege checks, durable queuing,
validation, CSRF, tagged history, reset preservation/conflicts, advisory-lock contention,
partial refresh results, cancellation and restart recovery. No live-source dependency
is used in these regressions; the deployed queue is smoke-tested separately.
