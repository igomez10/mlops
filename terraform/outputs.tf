output "mlflow_url" {
  description = "MLflow tracking server URL"
  value       = google_cloud_run_v2_service.mlflow.uri
}

output "fastapi_url" {
  description = "FastAPI service URL"
  value       = google_cloud_run_v2_service.fastapi.uri
}

output "gcs_images_bucket" {
  description = "GCS bucket for post image uploads; set as GCS_IMAGES_BUCKET for the API (also injected on Cloud Run)"
  value       = google_storage_bucket.mlops_images.name
}

output "ui_url" {
  description = "eBay Operator UI (static React) on Cloud Run"
  value       = google_cloud_run_v2_service.ui.uri
}
