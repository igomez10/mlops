output "mlflow_url" {
  description = "MLflow tracking server URL"
  value       = google_cloud_run_v2_service.mlflow.uri
}

output "fastapi_url" {
  description = "App URL: FastAPI + static React UI (same service)"
  value       = google_cloud_run_v2_service.fastapi.uri
}

output "gcs_images_bucket" {
  description = "GCS bucket for post image uploads; set as GCS_IMAGES_BUCKET for the API (also injected on Cloud Run)"
  value       = google_storage_bucket.mlops_images.name
}

output "firestore_database_id" {
  description = "Firestore database name used by the FastAPI service."
  value       = google_firestore_database.default.name
}

output "app_artifact_image" {
  description = "Artifact Registry image for the combined API + UI container"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/fastapi/fastapi"
}

output "cloudbuild_manual" {
  description = "From repo root: one-off build, push, and deploy the combined image to Cloud Run (fastapi)"
  value       = "gcloud builds submit --config=cloudbuild.yaml --project=${var.project_id}"
}
