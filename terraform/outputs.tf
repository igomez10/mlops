output "mlflow_url" {
  description = "MLflow tracking server URL"
  value       = google_cloud_run_v2_service.mlflow.uri
}

output "fastapi_url" {
  description = "FastAPI service URL"
  value       = google_cloud_run_v2_service.fastapi.uri
}
