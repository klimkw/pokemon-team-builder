# Adopt the existing Render + Neon deployment

Docker Compose remains the local development setup. This configuration adopts the
existing production resources; it does not provision replacements or alter tables.
Alembic still manages schema migrations. GitHub Actions still runs the daily scanner.

## Ownership and secret flow

```text
GitHub repository / Actions
  ├─ repository secret: PRODUCTION_DATABASE_URL ─┬─ daily scanner
  │                                            └─ Terraform → Render environment
  └─ infrastructure-production environment
       ├─ Render API key / Neon API key
       ├─ HCP Terraform token
       └─ nonsecret resource IDs, names, region, and app URL
            ↓
       import → plan → explicitly requested apply
            ↓
       HCP Terraform: persistent locked state, Local execution mode
```

GitHub is the place to enter and rotate input credentials. It is **not** the state
backend. Terraform state can contain Render environment values and Neon passwords,
including computed credentials retrieved during import. HCP stores this sensitive
state, and Render must retain the database URL to run the app. Marking a Terraform
variable sensitive hides its display; it does not remove it from state. No saved
plans, state files, or provider logs are published as GitHub artifacts or PR comments.
Do not enable TF_LOG or shell tracing on a production workflow.

Only two Terraform resources are managed: the Render web service and Neon project.
The Neon provider bundles its default branch, database, role and primary compute in
`neon_project`; don't import those defaults again as separate resources. The initial
configuration preserves existing topology, compute sizing, Postgres version and
branch protection and backup-history retention. Render notification/preview preferences
are also preserved. Additional branches/databases/roles are outside this initial
scope. Confirm the production connection points at the intended branch in Neon.
Application accounts, passwords, team data and local volumes are not imported.

## 1. Set up remote state once

1. Sign in at https://app.terraform.io and create an HCP Terraform organization.
2. Create a CLI-driven workspace named `pokemon-team-builder-production`.
3. In that workspace's Settings > General, set **Execution Mode: Local**. GitHub
   runs Terraform; HCP supplies state storage and locking. Do not connect the workspace
   to VCS or enable auto-apply. Set Terraform version to **1.13.5** if prompted.
4. Create a user API token with access to this workspace. Enter it directly in
   GitHub as `TF_API_TOKEN` below. Don't save tokens in tracked files or this chat.
5. Keep state access private and remote-state sharing disabled unless required.

The HCP Free plan currently covers up to 500 managed resources; this root module
has two. Confirm the plan selected in your account rather than selecting a paid tier.

## 2. Configure GitHub secret management

In repository **Settings > Secrets and variables > Actions > Secrets**, create:

| Repository secret | Value |
| --- | --- |
| `PRODUCTION_DATABASE_URL` | Existing direct/unpooled Neon URL, with `sslmode=require` or `sslmode=verify-full` |

This one repository secret is consumed by both the infrastructure workflow and the
scanner. If the existing `production` environment already has a secret with the
same name, it overrides the repository value: remove that duplicate after copying
the correct URL to the repository secret, or keep both deliberately synchronized.
The scanner's `production` environment must still exist. It has no infrastructure
API credentials and should permit unattended scheduling.

Next create **Settings > Environments > infrastructure-production**. Restrict
its deployment branches to `main`. Configure required reviewers if your GitHub
plan/repository visibility supports them; the apply fingerprint is required either
way. Keep this environment separate from `production`, so approval requirements
do not block the daily scanner.

Add these **environment secrets**:

| Environment secret | Obtain it from |
| --- | --- |
| `RENDER_API_KEY` | Render account settings > API Keys; a key authorized for the existing workspace |
| `NEON_API_KEY` | Neon account/organization API Keys; access to the existing project |
| `TF_API_TOKEN` | HCP Terraform user API token from step 1 |
| `RENDER_EXTRA_ENV_VARS_JSON` (optional) | JSON object of any additional existing Render variables you want to preserve |

Do not make API keys repository Variables. `RENDER_EXTRA_ENV_VARS_JSON` is optional;
for example an existing extra runtime credential must be entered here as a secret
JSON object, not in the Terraform source. The required application settings in
`main.tf` take precedence over this object.

Add these **environment Variables** (nonsecret):

| Variable | Value |
| --- | --- |
| `TF_CLOUD_ORGANIZATION` | Exact HCP organization name |
| `TF_WORKSPACE` | `pokemon-team-builder-production` |
| `RENDER_OWNER_ID` | Existing Render workspace owner ID (`usr-...` or `tea-...`), not the service ID |
| `RENDER_SERVICE_ID` | Existing service ID; the service shared in this chat was `srv-dbc3if1srm7s739hmh5g`—verify before using |
| `RENDER_SERVICE_NAME` | Exact existing service name |
| `RENDER_REGION` | Existing region slug: `virginia`, `ohio`, `oregon`, `frankfurt`, or `singapore` |
| `RENDER_PLAN` | `free`, or the actual existing plan if you intentionally upgraded it |
| `NEON_PROJECT_ID` | Existing project ID; the project shared in this chat was `shiny-moon-16690679`—verify before using |
| `NEON_PROJECT_NAME` | Exact project display name in Neon, which can differ from its ID |
| `APP_ORIGIN` | Actual existing public HTTPS origin, without a trailing slash |

Render's owner ID is available from its workspace/API metadata; do not substitute
`srv-...`. Names and regions must match existing resources. GitHub masks input secrets,
but contributors who can change main-branch workflows can use those secrets: protect
main and review workflow changes as production code.

## 3. Publish the configuration and import

Push these files to `main` after reviewing them. The **Terraform checks** workflow
runs formatting, schema validation, mocked plans and workflow-policy tests without
production credentials. It never imports or applies resources.

Then open **Actions > Production infrastructure > Run workflow**, branch **main**:

1. Choose `import` and run it.
2. If the infrastructure environment requires approval, approve the run.
3. The workflow connects to the HCP state and runs the equivalent of:

   ```sh
   terraform import neon_project.production shiny-moon-16690679
   terraform import render_web_service.app srv-dbc3if1srm7s739hmh5g
   ```

   These commands are illustrative; the workflow reads your verified IDs from
   GitHub Variables and credentials from secrets. You do not need a local Terraform
   installation or to copy production credentials onto your workstation.
4. Import adopts resources into state **without applying infrastructure changes**.
   It skips resources already imported with matching IDs, so a partially failed
   import can be retried. An existing mismatched ID stops the run.
5. Run the workflow again with action `plan`. It refuses to plan or apply until
   both resources have been imported.

Do not use import blocks together with an initial apply: that can combine adoption
with unintended configuration updates. The workflow keeps these operations separate.

## 4. Review the first plan and hand ownership to Terraform

The job summary lists resources/actions, changed fields, and a plan fingerprint.
Environment variable **names** are shown; their values are withheld. Compare the
committed configuration and GitHub settings to the current deployment. Aim for a
no-op baseline, or explicitly reconcile each expected difference first. Pay special
attention to region, plan, repository/branch, Dockerfile, and existing extra env vars.
If an extra Render variable would be removed, preserve it in the optional secret
above or extend the configuration before applying.

Creation, deletion and replacement are blocked by the runner, and both resources
also have `prevent_destroy`. A mismatched region must be corrected, not worked around
by deleting/recreating the service or removing lifecycle protection.

If the service is Blueprint-managed, **disconnect its Blueprint or disable its sync
before the first Terraform apply**. In Render's Blueprints area use its disconnect
control; confirm it preserves the service. Do not delete the service or database.
Render documents that disconnecting leaves resources intact. For a manually created
service with no Blueprint, skip this step. Keep Git repository auto-deploy enabled;
this is separate from Blueprint syncing.

The root `render.yaml` remains a legacy bootstrap reference. After adoption, do not
create/reconnect a Blueprint from it or manage this service through two systems.

## 5. Apply a reviewed plan

Run **Production infrastructure** with:

- action: `apply`
- expected_plan_sha: the full fingerprint from the reviewed `plan` run

It computes a fresh plan. Only an identical fingerprint is applied; if state,
configuration or secrets changed, it stops and shows a new summary to review. No
plan file survives the runner. Terraform state locking and Actions concurrency
serialize infrastructure operations. Changes to Render settings may redeploy the app.

After apply, verify `/api/health`, login, saved teams, and the public app. Trigger
**Production catalog scan** manually if the database has not been populated yet.
Keep schema migrations and catalog jobs out of Terraform.

## Rotation, maintenance and troubleshooting

- Rotate credentials at the provider, then update the matching GitHub secret. Updating
  a GitHub secret does **not** update Render automatically: run plan and apply for a
  changed database URL. The scanner uses the updated secret on its next run.
- HCP state retains historical secret values. Restrict access and treat old state
  versions as sensitive after rotation.
- The runner suppresses raw Terraform/provider output to avoid leaking imported
  secrets. Initialization errors show structured summaries/details with known input
  credentials redacted; state, plans and source snippets remain hidden.
  On failure first check all required settings, resource access, pinned
  versions, workspace Local mode, and state permissions. For detailed provider
  diagnosis, use a trusted private terminal with appropriate credentials and remote
  state access; do not upload raw state/plan/provider logs to an issue.
- If a replacement is proposed, match the existing configuration. Never destroy
  the database to make import succeed. Keep production data backups independently.
- To upgrade providers, change pins, regenerate `.terraform.lock.hcl`, and rerun
  validation and plan review. Existing application tests are unaffected by this patch.

## Local validation (no credentials)

With Terraform 1.13.5 installed:

```sh
terraform -chdir=infra/terraform init -backend=false -input=false
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform test -test-directory=tests
python -m unittest discover -s scripts/terraform -p 'test_*.py'
```

`.terraform/`, state, plans, real tfvars and crash logs are ignored. The provider
lockfile is tracked. Docker application builds exclude the infrastructure directory.

References:
- Render provider: https://render.com/docs/terraform-provider
- Render import: https://registry.terraform.io/providers/render-oss/render/1.9.1/docs/resources/web_service
- Neon project/import: https://registry.terraform.io/providers/kislerdm/neon/0.18.0/docs/resources/project
- HCP workspace settings: https://developer.hashicorp.com/terraform/cloud-docs/workspaces/settings
- HCP plans: https://developer.hashicorp.com/terraform/cloud-docs/overview
- Blueprint ownership: https://render.com/docs/infrastructure-as-code
