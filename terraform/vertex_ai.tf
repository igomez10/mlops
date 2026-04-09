resource "google_vertex_ai_endpoint" "linear_regression" {
  name         = "linear-regression-endpoint"
  display_name = "Toy Linear Regression Endpoint"
  location     = var.region
}
