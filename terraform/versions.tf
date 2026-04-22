terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.27"
    }
  }

  backend "gcs" {
    bucket = "mlops-492103-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google" {
  alias                 = "billing"
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}
