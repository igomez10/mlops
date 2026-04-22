# Project-level IAM for the default Cloud Build service account
# (used by gcloud builds submit with cloudbuild.yaml: push to AR, deploy Cloud Run).
data "google_project" "this" {
  project_id = var.project_id
}

locals {
  cloudbuild_sa = "${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

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
