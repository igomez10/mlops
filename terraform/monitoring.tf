resource "google_monitoring_notification_channel" "email" {
  display_name = "Email Alerts"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

# ── Billing ────────────────────────────────────────────────────────────────────

resource "google_billing_budget" "budget" {
  provider        = google.billing
  billing_account = var.billing_account_id
  display_name    = "MLOps Monthly Budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }

  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.email.id,
    ]
    disable_default_iam_recipients = false
  }

  lifecycle {
    ignore_changes = [budget_filter[0].projects]
  }
}

# ── Cloud Run 5xx errors ───────────────────────────────────────────────────────

resource "google_monitoring_alert_policy" "cloud_run_5xx" {
  display_name = "Cloud Run — 5xx Errors"
  combiner     = "OR"

  conditions {
    display_name = "5xx response rate"
    condition_threshold {
      filter          = <<-EOT
        resource.type = "cloud_run_revision"
        AND metric.type = "run.googleapis.com/request_count"
        AND metric.labels.response_code_class = "5xx"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Cloud Run logged errors ────────────────────────────────────────────────────

resource "google_monitoring_alert_policy" "cloud_run_log_errors" {
  display_name = "Cloud Run — Log Errors"
  combiner     = "OR"

  conditions {
    display_name = "ERROR severity logs"
    condition_matched_log {
      filter = <<-EOT
        resource.type = "cloud_run_revision"
        AND severity >= ERROR
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "300s"
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Cloud Run CPU utilization ──────────────────────────────────────────────────

resource "google_monitoring_alert_policy" "cloud_run_cpu" {
  display_name = "Cloud Run — High CPU Utilization"
  combiner     = "OR"

  conditions {
    display_name = "CPU utilization > 80%"
    condition_threshold {
      filter          = <<-EOT
        resource.type = "cloud_run_revision"
        AND metric.type = "run.googleapis.com/container/cpu/utilizations"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "120s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_PERCENTILE_99"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}
