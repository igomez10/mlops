# main.tf
# Entry point for GCP infrastructure resources.
# Provider configuration is in versions.tf.
# Variables are declared in variables.tf and set in terraform.tfvars.

resource "google_artifact_registry_repository" "mlflow" {
  repository_id = "mlflow"
  location      = var.region
  format        = "DOCKER"
}

resource "google_storage_bucket" "mlflow_artifacts" {
  name          = "${var.project_id}-mlflow-artifacts"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}
