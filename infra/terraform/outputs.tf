output "application_url" {
  value = render_web_service.app.url
}

output "neon_project_id" {
  value = neon_project.demo.id
}
