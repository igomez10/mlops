variable "project_id" {
  description = "The GCP project ID to deploy resources into."
  type        = string
}

variable "region" {
  description = "The default GCP region for resources."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The default GCP zone for zonal resources."
  type        = string
  default     = "us-central1-a"
}

variable "billing_account_id" {
  description = "The GCP billing account ID linked to this project."
  type        = string
}

variable "budget_amount_usd" {
  description = "Monthly budget threshold in USD before alerts fire."
  type        = number
  default     = 50
}

variable "alert_email" {
  description = "Email address to receive monitoring alerts."
  type        = string
}

# Optional: GitHub → Cloud Build trigger (install the Cloud Build GitHub App first).
variable "github_ui_build_enabled" {
  description = "If true, create a Cloud Build trigger to run cloudbuild.yaml on push to the given branch."
  type        = bool
  default     = false
}

variable "github_ui_owner" {
  description = "GitHub org or user (for the UI deploy trigger only)."
  type        = string
  default     = ""
}

variable "github_ui_repo" {
  description = "GitHub repository name (for the UI deploy trigger only)."
  type        = string
  default     = ""
}

variable "github_ui_branch" {
  description = "Regex for branch, e.g. ^main$ (for the UI deploy trigger only)."
  type        = string
  default     = "^main$"
}
