# Demo: Render + Neon + GitHub Actions

Local development remains `docker compose up --build`. Its Dockerfiles, Nginx,
volumes, and scanner processes are separate from this deployment.

Demo topology:

- Render builds `Dockerfile.demo`: React assets and FastAPI in one service.
- Neon stores accounts, sessions, teams, catalog, change history, and scan audits.
- GitHub Actions runs a one-shot scanner daily at 10:23 UTC and on manual request.
- No local database files, accounts, or volumes are uploaded.

## 1. Create Neon

Create a demo project at https://neon.com, ideally in the same region as Render.
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

The Blueprint sets secure cookies and enables bounded request-mode demo controls. Root context is `.`,
Dockerfile is `./Dockerfile.demo`, health check is `/api/health`, and the image
listens on Render's `PORT`. No disk, Render database, or scanner service is created.

Startup runs `alembic upgrade head` before accepting requests. This supports the
single-instance free deployment; do not scale replicas without moving migrations to
an explicitly coordinated release step. Health currently verifies process liveness,
not database availability. Never run a destructive schema reset to fix a failed deploy.

Terraform and the bootstrap Blueprint set the deploy trigger to **After CI Checks
Pass** (`checksPass`). For an existing service, run the infrastructure plan/apply
procedure below before relying on this gate. Render waits for detected checks on the
commit; a failed check prevents automatic deployment. Manual deploys bypass this gate.
Both Tests jobs run on every deployment-branch push: the full application suite and
the demo-image smoke check. The latter uses a fresh disposable PostgreSQL DB,
real startup migrations, demo cookie settings, and synthetic catalog fixtures.
It makes no requests to the live service. Keep schema changes backward compatible
with the previous release.

## 4. Configure and run the scanner

In GitHub **Settings > Environments**, create `demo`. Add environment secret
`DEMO_DATABASE_URL` with the same direct Neon URL. Allow only the deployment
branch to use this environment. If you add required human approval, scheduled runs
will wait for that approval; omit approval requirements for unattended daily scans.

After Render has successfully run migrations, open **Actions > Demo catalog
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
queue worker. Request mode rejects `/api/admin/refresh` with instructions to use
GitHub's manual scanner workflow. Signed-in users can apply/reset bounded demo
changes within the HTTP request; no background worker is needed for those actions.

If you need admin queue processing, add a paid Render background worker using root
context `.`, `Dockerfile.demo`, the same direct `DATABASE_URL`, and Docker
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
blindly downgrade or delete the demo database.

## Adopt existing infrastructure into Terraform

For an existing Render/Neon deployment, follow [infra/terraform/README.md](../infra/terraform/README.md).
It keeps demo credentials in GitHub secret settings and persistent state in
HCP Terraform. Disconnect Blueprint syncing before Terraform applies service changes;
keep Docker Compose for local development.

## Activate the CI deployment gate on the existing service

After the release-check changes are pushed and both Tests jobs pass:

1. Run **Actions → Demo infrastructure → Run workflow**, selecting `plan`.
2. Confirm the Render change sets `docker.auto_deploy_trigger` from `commit` to
   `checksPass`, with no creation, deletion or replacement. Review any other drift.
3. Run it again with `apply` and the exact plan fingerprint from that new plan.
4. Confirm Render **Settings → Auto-Deploy → After CI Checks Pass**. No new secret
   is needed. Subsequent pushes deploy after their CI checks pass.

A passing CI image check validates packaging and application behavior in isolation;
it cannot verify live Neon credentials, Render configuration or provider availability.
After a deployment, check the public URL, sign in, and inspect App info for catalog
freshness. Use the scanner workflow's run history and failure notifications for daily
job status. No automated restore drill or proactive stale-scan monitor is configured.

For rollback, select the last known working Render deployment only when its code is
compatible with the current schema. Prefer a forward fix for schema changes. Before
a risky migration, confirm the Neon recovery window and take an appropriate backup;
test a restore to a separate branch/database before depending on that recovery path.
The current free deployment does not provide a tested disaster-recovery guarantee.

## Rename existing account-side settings safely

Deployment files and workflows now use **demo** names. Existing resources are retained:

1. In GitHub, create environment `demo` and copy the app environment settings from
   `production`. Set repository variable `DEMO_APP_ENVIRONMENT=demo` only after the
   new environment is ready. Until then, workflows use the existing environment.
2. Create environment `infrastructure-demo` and copy the infrastructure secrets and
   variables from `infrastructure-production`. Secret values cannot be read back;
   use the originals or rotate the credentials if needed. Set repository variable
   `DEMO_INFRA_ENVIRONMENT=infrastructure-demo` when ready.
3. Add `DEMO_DATABASE_URL` with the same direct Neon URL wherever the old database
   secret was stored. Workflows temporarily fall back to `PRODUCTION_DATABASE_URL`.
   Remove the old secret after a successful manual demo scan and infrastructure plan.
4. Rename the existing HCP workspace to `pokemon-team-builder-demo` in its settings,
   then update `TF_WORKSPACE` in the active infrastructure GitHub environment. Rename
   the existing workspace; do not create an empty workspace or discard its state.
5. Run **Demo infrastructure → plan**. The plan should move `neon_project.production`
   to `neon_project.demo`, update the Dockerfile path to `./Dockerfile.demo`, enable
   demo controls and select request execution. It must not recreate resources.
   Review all changes and apply using the new fingerprint.

The public Render URL and Render/Neon resource IDs stay the same. Their display names
already use `pokemon-team-builder`. Old run history retains its historical labels.
The legacy environment names and secret fallback are migration bridges; delete the old
GitHub environments after both demo workflows have been verified with the new ones.

## Shared demo controls

Any active signed-in user may apply or reset demo changes when
`ENABLE_DEMO_CONTROLS=true`. These operations change the shared catalog for all users;
reset can undo another reviewer's demo. They keep origin checks, audit records and
scan locking. Full refresh and job-history endpoints still require a superuser.
Hosted `DEMO_EXECUTION_MODE=request` executes bounded demo operations without a worker;
local Compose retains its queue worker. Daily real-source refresh remains in Actions.

`Dockerfile.production` temporarily mirrors `Dockerfile.demo` so the existing Render
Dockerfile setting still builds during this transition. After the demo Dockerfile path
has been applied and deployed successfully, remove that compatibility file.

## Retiring the former shared reviewer login

The provisioning CLI and manual workflow for the former shared reviewer account
have been removed. Demo apply/reset continues to use normal signed-in accounts
when demo controls are enabled.

Deploying this revision runs `0006_retire_reviewer` through the usual Alembic startup
step. It targets only the reserved reviewer UUID, revokes its sessions and superuser
access, and cancels its queued jobs. If it has no teams, job records or alert-read
markers, the account is deleted. Otherwise it remains inactive to preserve those
records. Personal accounts named `admin` are not matched by name and are untouched.
No shared login is recreated on downgrade. Applying the migration, rather than
removing files alone, is what retires an account that was already provisioned.
