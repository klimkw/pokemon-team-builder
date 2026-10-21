mock_provider "render" {}
mock_provider "neon" {}

variables {
  render_service_name = "existing-app"
  render_region       = "virginia"
  app_origin          = "https://existing-app.onrender.com"
  neon_project_name   = "existing-catalog"
  database_url        = "postgresql://dummy:dummy@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require"
}

run "demo_configuration" {
  command = plan
  assert {
    condition     = render_web_service.app.plan == "free"
    error_message = "The initial configuration must preserve the free plan."
  }
  assert {
    condition     = render_web_service.app.runtime_source.docker.dockerfile_path == "./Dockerfile.demo"
    error_message = "Render must build the combined demo image."
  }
  assert {
    condition     = render_web_service.app.runtime_source.docker.auto_deploy_trigger == "checksPass"
    error_message = "Demo deploys must wait for CI checks to pass."
  }
  assert {
    condition     = render_web_service.app.env_vars["COOKIE_SECURE"].value == "true" && render_web_service.app.env_vars["ENABLE_DEMO_CONTROLS"].value == "true" && render_web_service.app.env_vars["DEMO_EXECUTION_MODE"].value == "request"
    error_message = "Demo needs HTTPS cookies and bounded request-mode reviewer demos."
  }
}

run "reject_pooled_scanner_connection" {
  command = plan
  variables {
    database_url = "postgresql://dummy:dummy@ep-example-pooler.neon.tech/neondb?sslmode=require"
  }
  expect_failures = [var.database_url]
}

run "reject_plaintext_database_connection" {
  command = plan
  variables {
    database_url = "postgresql://dummy:dummy@ep-example.neon.tech/neondb"
  }
  expect_failures = [var.database_url]
}

run "reject_non_https_origin" {
  command = plan
  variables {
    app_origin = "http://existing-app.onrender.com"
  }
  expect_failures = [var.app_origin]
}
