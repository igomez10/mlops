# MLOps

End-to-end ML platform on GCP using MLflow for experiment tracking and FastAPI for model serving, with infrastructure managed by Terraform.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   GCP (us-central1)                 │
│                                                     │
│  ┌──────────────┐        ┌──────────────────────┐   │
│  │  Cloud Run   │        │      Cloud Run       │   │
│  │   MLflow     │◄───────│      FastAPI         │   │
│  │  (tracking)  │        │   (model serving)    │   │
│  └──────┬───────┘        └──────────────────────┘   │
│         │                                           │
│  ┌──────┴───────┐  ┌──────────────────────────┐     │
│  │  GCS Bucket  │  │  Artifact Registry       │     │
│  │  (artifacts) │  │  mlflow / fastapi images │     │
│  └──────────────┘  └──────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Vertex AI — linear-regression-endpoint      │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Services

| Service | URL |
|---------|-----|
| MLflow  | https://mlflow-34676207684.us-central1.run.app |
| FastAPI | https://fastapi-34676207684.us-central1.run.app |

## Repository Layout

```
.
├── server.py              # FastAPI application
├── Dockerfile.fastapi     # FastAPI container image
├── docker-compose.yml     # Local dev stack (MLflow + FastAPI)
├── requirements.txt       # Python dependencies
├── Makefile               # All common operations
├── notebook.ipynb         # Experimentation notebook
└── terraform/
    ├── main.tf            # Cloud Run, GCS, Artifact Registry
    ├── vertex_ai.tf       # Vertex AI endpoint
    ├── monitoring.tf      # Alerts and billing budget
    ├── outputs.tf
    ├── variables.tf
    └── versions.tf
```

## FastAPI Endpoints

Defined in `server.py`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Welcome message |
| GET | `/health` | Health check |
| POST | `/predict` | Run model inference |
| POST | `/add_query_parameters` | Add two numbers (query params) |
| POST | `/add_body_parameters` | Add two numbers (body) |

### `/predict` request/response

```bash
curl -X POST https://fastapi-34676207684.us-central1.run.app/predict \
  -H "Content-Type: application/json" \
  -d '{"sqft": 1500, "rooms": 3}'
```

```json
{"prediction": 1234}
```

The model is loaded from MLflow at startup via `MLFLOW_MODEL_URI`. Cold starts are slow; subsequent requests are fast.

## Running Locally

### Without Docker

```bash
MLFLOW_TRACKING_URI=https://mlflow-34676207684.us-central1.run.app \
MLFLOW_MODEL_URI=runs:/6736c234459f44769f3475477b730f89/model \
make run-fastapi
```

### With Docker Compose (MLflow + FastAPI)

```bash
make build-fastapi
MLFLOW_MODEL_URI=runs:/6736c234459f44769f3475477b730f89/model \
make start-docker-compose
```

MLflow will be available at http://localhost:5001 and FastAPI at http://localhost:8000.

## Infrastructure (Terraform)

All GCP resources are defined in `terraform/` and managed with:

```bash
make tf-plan    # preview changes
make tf-apply   # apply changes
```

### Resources

| Resource | Name |
|----------|------|
| Artifact Registry | `mlflow`, `fastapi` (Docker) |
| GCS Bucket | `mlops-492103-mlflow-artifacts` (model artifacts) |
| GCS Bucket | `mlops-492103-mlflow-db` (MLflow backend store via SQLite) |
| Cloud Run | `mlflow` (2 CPU, 2Gi RAM, max 1 instance) |
| Cloud Run | `fastapi` (1 CPU, 512Mi RAM) |
| Vertex AI Endpoint | `linear-regression-endpoint` |

Both Cloud Run services use CPU throttling and scale to zero when idle.

## Docker Images

Images are stored in GCP Artifact Registry (`us-central1-docker.pkg.dev/mlops-492103/`).

```bash
# Build and push FastAPI image
make push-fastapi

# Pull official MLflow image and push to registry
make push-mlflow

# Redeploy services on Cloud Run
make redeploy-fastapi
make redeploy-mlflow
```

## Vertex AI

A sklearn linear regression model can be uploaded and deployed to Vertex AI:

```bash
make vertex-deploy-toy-model    # upload model artifact and deploy to endpoint
make vertex-undeploy-toy-model  # remove deployed model from endpoint
```

Model artifact is read from `gs://mlops-492103-mlflow-artifacts/models/linear-regression/`.

## Monitoring & Alerts

Defined in `terraform/monitoring.tf`. Alerts fire to the configured email on:

- **5xx errors** — any Cloud Run 5xx response in the last 60s
- **Log errors** — `severity >= ERROR` in Cloud Run logs (rate-limited to 1 alert per 5 min)
- **High CPU** — p99 CPU utilization > 80% for 2 minutes on any Cloud Run service
- **Billing budget** — alerts at 50% and 100% of the $50/month budget
- **I dont like pizza**
