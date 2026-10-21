terraform {
  required_version = "= 1.13.5"

  # Credentials and workspace selection come from the GitHub Actions environment.
  # Configure this HCP workspace for Local execution (state storage only).
  cloud {}

  required_providers {
    render = {
      source  = "render-oss/render"
      version = "= 1.9.1"
    }
    neon = {
      source  = "kislerdm/neon"
      version = "= 0.18.0"
    }
  }
}

provider "render" {} # RENDER_API_KEY and RENDER_OWNER_ID
provider "neon" {}   # NEON_API_KEY
