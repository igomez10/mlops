# main.tf
# Entry point for GCP infrastructure resources.
# Provider configuration is in versions.tf.
# Variables are declared in variables.tf and set in terraform.tfvars.

resource "google_artifact_registry_repository" "mlflow" {
  repository_id = "mlflow"
  location      = var.region
  format        = "DOCKER"
}
