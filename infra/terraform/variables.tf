variable "render_service_name" {
  type        = string
  description = "Exact existing Render service name."
}

variable "render_region" {
  type        = string
  description = "Existing Render region slug; changing regions can require replacement."
  validation {
    condition     = contains(["frankfurt", "ohio", "oregon", "singapore", "virginia"], var.render_region)
    error_message = "Use the existing Render region slug."
  }
}

variable "render_plan" {
  type        = string
  description = "Existing service plan; default preserves the intended free deployment."
  default     = "free"
}

variable "repository_url" {
  type    = string
  default = "https://github.com/klimkw/pokemon-team-builder"
}

variable "deploy_branch" {
  type    = string
  default = "main"
}

variable "app_origin" {
  type        = string
  description = "Exact existing public HTTPS origin, without a trailing slash."
  validation {
    condition     = can(regex("^https://[^/]+$", var.app_origin))
    error_message = "Use an HTTPS origin without a path or trailing slash."
  }
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "Direct Neon URL, supplied from GitHub PRODUCTION_DATABASE_URL."
  validation {
    condition = (
      can(regex("^postgres(ql)?(\\+asyncpg)?://", var.database_url)) &&
      !can(regex("-pooler\\.", var.database_url)) &&
      can(regex("[?&]sslmode=(require|verify-full)(&|$)", var.database_url))
    )
    error_message = "Use a direct PostgreSQL URL with sslmode=require or verify-full."
  }
}

variable "neon_project_name" {
  type        = string
  description = "Exact existing Neon project display name."
}

variable "additional_render_env_vars" {
  type        = map(string)
  sensitive   = true
  default     = {}
  description = "Optional existing Render settings to preserve, from GitHub RENDER_EXTRA_ENV_VARS_JSON. Required application settings take precedence."
}
