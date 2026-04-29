# main.tf
# Entry point for GCP infrastructure resources.
# Provider configuration is in versions.tf.
# Variables are declared in variables.tf and set in terraform.tfvars.

locals {
  # CORS: local Vite (5173/5174). Deployed app is same origin as the API, so no extra origin.
  fastapi_cors_origins = join(",", [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
  ])
}

resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id}-terraform-state"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_service" "firestore" {
  project = var.project_id
  service = "firestore.googleapis.com"
}

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.firestore]
}

resource "google_artifact_registry_repository" "mlflow" {
  repository_id = "mlflow"
  location      = var.region
  format        = "DOCKER"
}

resource "google_artifact_registry_repository" "fastapi" {
  repository_id = "fastapi"
  location      = var.region
  format        = "DOCKER"
}

resource "google_artifact_registry_repository_iam_member" "mlflow_ar_reader" {
  location   = var.region
  repository = google_artifact_registry_repository.mlflow.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.mlflow.email}"
}

resource "google_storage_bucket" "mlflow_artifacts" {
  name          = "${var.project_id}-mlflow-artifacts"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}

resource "google_service_account" "mlflow" {
  account_id   = "mlflow-cloudrun"
  display_name = "MLflow Cloud Run Service Account"
}

resource "google_storage_bucket_iam_member" "mlflow_artifacts_reader" {
  bucket = google_storage_bucket.mlflow_artifacts.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.mlflow.email}"
}

resource "google_storage_bucket" "mlflow_db" {
  name          = "${var.project_id}-mlflow-db"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "mlflow_db_writer" {
  bucket = google_storage_bucket.mlflow_db.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.mlflow.email}"
}

resource "google_cloud_run_v2_service" "mlflow" {
  name     = "mlflow"
  location = var.region

  template {
    service_account = google_service_account.mlflow.email

    scaling {
      max_instance_count = 1
    }

    containers {
      image   = "${var.region}-docker.pkg.dev/${var.project_id}/mlflow/mlflow:v3.10.1-full"
      command = ["mlflow"]
      args = [
        "server",
        "--host", "0.0.0.0",
        "--port", "5000",
        "--default-artifact-root", "gs://${var.project_id}-mlflow-artifacts",
        "--backend-store-uri", "/data",
        "--allowed-hosts", "*",
        "--cors-allowed-origins", "*",
        "--serve-artifacts",
      ]

      env {
        name  = "MLFLOW_SERVER_ALLOWED_HOSTS"
        value = "*"
      }

      resources {
        cpu_idle          = true
        startup_cpu_boost = true
        limits = {
          memory = "2Gi"
          cpu    = "2"
        }
      }

      ports {
        container_port = 5000
      }

      volume_mounts {
        name       = "sqlite-data"
        mount_path = "/data"
      }
    }

    volumes {
      name = "sqlite-data"
      gcs {
        bucket    = google_storage_bucket.mlflow_db.name
        read_only = false
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "mlflow_public" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_service_account" "fastapi" {
  account_id   = "fastapi-cloudrun"
  display_name = "FastAPI Cloud Run Service Account"
}

resource "google_project_iam_member" "fastapi_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.fastapi.email}"
}

resource "google_storage_bucket_iam_member" "fastapi_artifacts_reader" {
  bucket = google_storage_bucket.mlflow_artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.fastapi.email}"
}

# Post images for the FastAPI UI (private; served via API GET /images/...).
resource "google_storage_bucket" "mlops_images" {
  name     = "${var.project_id}-mlops-images"
  location = var.region

  force_destroy               = false
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "mlops_images_fastapi_writer" {
  bucket = google_storage_bucket.mlops_images.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.fastapi.email}"
}

# Images are private; the FastAPI service reads via objectUser and serves GET /images/...

resource "google_cloud_run_v2_service" "fastapi" {
  name     = "fastapi"
  location = var.region

  depends_on = [google_firestore_database.default]

  template {
    service_account = google_service_account.fastapi.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/fastapi/fastapi:latest"

      env {
        name  = "MLFLOW_TRACKING_URI"
        value = google_cloud_run_v2_service.mlflow.uri
      }

      env {
        name  = "MLFLOW_MODEL_URI"
        value = "runs:/6736c234459f44769f3475477b730f89/model"
      }

      env {
        name  = "GCS_IMAGES_BUCKET"
        value = google_storage_bucket.mlops_images.name
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "POSTS_BACKEND"
        value = "firestore"
      }

      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = google_firestore_database.default.name
      }

      env {
        name  = "CORS_ORIGINS"
        value = local.fastapi_cors_origins
      }

      resources {
        cpu_idle          = true
        startup_cpu_boost = true
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }

      ports {
        container_port = 8000
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "fastapi_public" {
  name     = google_cloud_run_v2_service.fastapi.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
