# Production: Render + Neon + GitHub Actions

Local development remains `docker compose up --build`. Its Dockerfiles, Nginx,
volumes, and scanner processes are separate from this deployment.

Production topology:

- Render builds `Dockerfile.production`: React assets and FastAPI in one service.
- Neon stores accounts, sessions, teams, catalog, change history, and scan audits.
- GitHub Actions runs a one-shot scanner daily at 10:23 UTC and on manual request.
- No local database files, accounts, or volumes are uploaded.

## 1. Create Neon

Create a production project at https://neon.com, ideally in the same region as Render.
In **Connect**, disable connection pooling and copy the PostgreSQL URL. Use this
**direct** URL for both Render and the scheduled job: scanner advisory locks require
session affinity, and startup migrations also use this connection.

The app accepts Neon's `postgresql://...?...sslmode=require&channel_binding=require`
URL. It selects asyncpg, translates sslmode to a TLS context with certificate and
hostname validation, and removes the libpq-only channel_binding option. It does not
provide SCRAM channel binding; certificate and hostname verification remain required.
Keep `sslmode=require` (or `verify-full`) on the URL. Do not paste credentials into
tracked files, issue comments, screenshots, or build arguments.

## 2. Push this deployment patch to GitHub

Review and commit the deployment files together with the application version you
intend to publish, then push to your deployment branch. Do not commit `.env`.
The scanner workflow must be on the repository's default branch to run on schedule.

## 3. Create the Render service

At https://dashboard.render.com select **New > Blueprint**, connect the GitHub
repository and deployment branch, and use the root `render.yaml`.

The Blueprint creates one free Docker web service, and prompts for:

- `DATABASE_URL`: direct Neon PostgreSQL URL above.
- `APP_ORIGIN`: expected public HTTPS URL, with no trailing slash. Initially use
  `https://pokemon-team-builder.onrender.com` if available; after creation, compare
  against the actual assigned URL and correct the value in the service's Environment
  settings if Render adds a suffix. Redeploy after correcting it. Login and mutations
  will be rejected until the origin matches.

The Blueprint sets secure cookies and disables demo controls. Root context is `.`,
Dockerfile is `./Dockerfile.production`, health check is `/api/health`, and the image
listens on Render's `PORT`. No disk, Render database, or scanner service is created.

Startup runs `alembic upgrade head` before accepting requests. This supports the
single-instance free deployment; do not scale replicas without moving migrations to
an explicitly coordinated release step. Health currently verifies process liveness,
not database availability. Never run a destructive schema reset to fix a failed deploy.

Render deploys repository pushes independently of GitHub CI by default. For a reviewed
release, merge only after the Tests workflow passes; do not assume the Blueprint gates
publication on CI. Keep schema changes backward compatible with the previous release.

## 4. Configure and run the scanner

In GitHub **Settings > Environments**, create `production`. Add environment secret
`PRODUCTION_DATABASE_URL` with the same direct Neon URL. Allow only the deployment
branch to use this environment. If you add required human approval, scheduled runs
will wait for that approval; omit approval requirements for unattended daily scans.

After Render has successfully run migrations, open **Actions > Production catalog
scan > Run workflow**, select the deployed branch, and run it. The first successful
scan populates both Pokemon and type relations. It does not create user accounts.

The workflow builds the existing backend image with locked dependencies, overrides
its startup command, and runs `python -m app.jobs.scanner` once. It does not run
migrations or a resident scheduler. Later it runs at 10:23 UTC daily (06:23 Eastern
in daylight saving time, 05:23 in standard time). GitHub can delay scheduled jobs;
this is not a precise-time service. Concurrency and the existing database advisory
lock prevent overlapping writes. Failed/partial scans exit nonzero; inspect the
Actions summary and scan audit, and rerun manually after resolving the cause.
Enable GitHub Actions failure notifications in your account notification settings.

Deploy compatible application/schema changes before scanner changes reach the
default branch: Actions executes default-branch code, not necessarily Render's last
successful deployed commit. Avoid running incompatible scanner code against an old
schema after a failed deployment.

## Admin queue versus daily scans

This free setup schedules live catalog scans. It does **not** run the durable admin
queue worker. An admin `/api/admin/refresh` request would stay queued; use GitHub's
manual scanner workflow for refreshes instead. Demo controls are disabled.

If you need admin queue processing, add a paid Render background worker using root
context `.`, `Dockerfile.production`, the same direct `DATABASE_URL`, and Docker
command `python -m app.jobs.worker` (without `--schedule`). Keep demo controls false.
Only the GitHub workflow should own periodic scans in that arrangement. Do not start
an always-on worker in the web service or use a sleeping web service as a scheduler.

## 5. Verify the deployment

- Visit the public URL and `/api/health`.
- Confirm the catalog is populated after the first scan.
- Register a fresh account, log in, save a team, and generate counters.
- Log out and log back in; saved teams should persist.
- Redeploy the service and verify the same account and teams still exist.
- Manually run the scanner again; unchanged source records should not duplicate history.
- Confirm unknown `/api` routes return 404, not the frontend HTML.

## Costs, operational limits, and rollback

Render free web services sleep after 15 idle minutes. The initial page itself may
wait while the service wakes; retry after startup if it fails. This build serves
frontend and API together, so an already-loaded tab may encounter the existing
15-second request timeout when waking the service. No automatic retries of writes
are added, since their outcome could be ambiguous.

Neon free usage has storage/compute limits. Public-repository standard Actions
runners are free; private repositories have a minute allowance. GitHub disables
public-repository schedules after 60 days without activity. Check current terms:

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://neon.com/pricing
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

Before opening registration widely, add login abuse protection/rate limiting.
Maintain database backups appropriate to the data's importance. Application rollback
on Render does not roll back database migrations; prefer forward fixes and never
blindly downgrade or delete the production database.

## Adopt existing infrastructure into Terraform

For an existing Render/Neon deployment, follow [infra/terraform/README.md](infra/terraform/README.md).
It keeps production credentials in GitHub secret settings and persistent state in
HCP Terraform. Disconnect Blueprint syncing before Terraform applies service changes;
keep Docker Compose for local development.
