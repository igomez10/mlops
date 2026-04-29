variable "project_id" {
  description = "The GCP project ID to deploy resources into."
  type        = string
}

variable "region" {
  description = "The default GCP region for resources."
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore database location. Use a Firestore-supported region or multi-region such as nam5."
  type        = string
  default     = "nam5"
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
