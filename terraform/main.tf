# main.tf
# Entry point for GCP infrastructure resources.
# Provider configuration is in versions.tf.
# Variables are declared in variables.tf and set in terraform.tfvars.

resource "google_artifact_registry_repository" "mlflow" {
  repository_id = "mlflow"
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
    service_account   = google_service_account.mlflow.email
    startup_cpu_boost = true

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
      ]

      env {
        name  = "MLFLOW_SERVER_ALLOWED_HOSTS"
        value = "*"
      }

      resources {
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
