# Optional one-shot trigger: on push, run cloudbuild.yaml (UI build + deploy to Cloud Run "ui").
# Prerequisite: connect your GitHub repo in Cloud Build (GitHub app) and grant the repo to this project.
# If you use Cloud Source Repositories instead, replace this with a v2 connection trigger.

resource "google_cloudbuild_trigger" "github_ui" {
  count     = var.github_ui_build_enabled && var.github_ui_owner != "" && var.github_ui_repo != "" ? 1 : 0
  name      = "ui-build-deploy-main"
  project   = var.project_id
  location  = "global"
  filename  = "cloudbuild.yaml"
  tags      = ["github", "ui"]
  # UI + shared config; add paths if the UI should also run when the API contract in server.py changes
  included_files = ["frontend/**", "cloudbuild.yaml"]

  github {
    owner = var.github_ui_owner
    name  = var.github_ui_repo
    push {
      branch = var.github_ui_branch
    }
  }

  substitutions = {
    _REGION = var.region
  }
}
