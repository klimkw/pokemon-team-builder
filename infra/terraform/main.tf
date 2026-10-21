# The imported project includes its default branch/database/role/compute. Do not
# also declare those same defaults as separately managed resources.
resource "neon_project" "production" {
  name = var.neon_project_name

  lifecycle {
    prevent_destroy = true
    # Adopt existing topology, Postgres version, and compute settings as-is.
    # This first iteration manages the project name, not database sizing.
    ignore_changes = [branch, primary_compute, region_id, pg_version, default_branch_protected, history_retention_seconds]
  }
}

resource "render_web_service" "app" {
  name              = var.render_service_name
  plan              = var.render_plan
  region            = var.render_region
  health_check_path = "/api/health"
  root_directory    = ""

  runtime_source = {
    docker = {
      repo_url            = var.repository_url
      branch              = var.deploy_branch
      dockerfile_path     = "./Dockerfile.production"
      context             = "."
      auto_deploy         = true
      auto_deploy_trigger = "checksPass"
    }
  }

  env_vars = merge(
    { for key, value in var.additional_render_env_vars : key => { value = value } },
    {
      DATABASE_URL                = { value = var.database_url }
      APP_ORIGIN                  = { value = var.app_origin }
      COOKIE_SECURE               = { value = "true" }
      ENABLE_DEMO_CONTROLS        = { value = "false" }
      DEMO_MODE                   = { value = "false" }
      CATALOG_SCAN_INTERVAL_HOURS = { value = "24" }
      CHANGE_ALERT_WINDOW_DAYS    = { value = "7" }
    }
  )

  lifecycle {
    prevent_destroy = true
    # These existing dashboard preferences are outside this adoption's scope.
    ignore_changes = [notification_override, previews, pull_request_previews_enabled]
  }
}
