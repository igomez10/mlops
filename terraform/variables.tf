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
