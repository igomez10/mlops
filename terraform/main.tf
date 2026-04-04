# main.tf
# Entry point for GCP infrastructure resources.
# Provider configuration is in versions.tf.
# Variables are declared in variables.tf and set in terraform.tfvars.

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
        startup_cpu_boost = true
        limits = {
          memory = "4Gi"
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

resource "google_storage_bucket_iam_member" "fastapi_artifacts_reader" {
  bucket = google_storage_bucket.mlflow_artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.fastapi.email}"
}

resource "google_cloud_run_v2_service" "fastapi" {
  name     = "fastapi"
  location = var.region

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

      resources {
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
