# Static React app on Cloud Run + Artifact Registry, plus Cloud Build permissions.

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  cloudbuild_sa = "${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
  # FastAPI CORS: local dev (Vite) + deployed UI origin
  fastapi_cors_origins = join(",", [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    trimsuffix(google_cloud_run_v2_service.ui.uri, "/"),
  ])
}

resource "google_artifact_registry_repository" "ui" {
  repository_id = "ui"
  location        = var.region
  format          = "DOCKER"
}

# Placeholder image until the first `gcloud builds submit` (or trigger) deploys the real image.
# Terraform ignores the image so Cloud Build can roll forward revisions without drift.
resource "google_cloud_run_v2_service" "ui" {
  name     = "ui"
  location = var.region

  template {
    scaling {
      max_instance_count = 2
    }

    containers {
      # Public sample: listens on 8080. Replaced on first successful Cloud Build.
      image = "gcr.io/google-samples/hello-app:1.0"
      resources {
        cpu_idle = true
        limits = {
          memory = "256Mi"
          cpu    = "1"
        }
      }
      ports {
        container_port = 8080
      }
    }
  }

  lifecycle {
    ignore_changes = [
      # gcloud / Cloud Build own the image digest after the first real deploy
      template[0].containers[0].image,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "ui_public" {
  name     = google_cloud_run_v2_service.ui.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Allow the default Cloud Build service account to push images and deploy Cloud Run.
resource "google_project_iam_member" "cloudbuild_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}

resource "google_project_iam_member" "cloudbuild_artifactregistry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}

resource "google_project_iam_member" "cloudbuild_service_account_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}
