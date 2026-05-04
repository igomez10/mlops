# MLOps

This repository currently contains a FastAPI backend for image-based post creation and eBay draft/publish flows, a React frontend, and Terraform for the GCP environment.

## Active Components

- `server.py`: main FastAPI application
- `pkg/`: backend adapters and domain helpers
- `product_analyzer/`: reusable image analysis package used by the backend
- `frontend/`: Vite + React UI
- `terraform/`: Cloud Run, storage, Vertex AI, and monitoring infrastructure

## Backend API

Main routes exposed by `server.py`:

- `GET /health`
- `GET /posts`
- `GET /posts/{post_id}`
- `POST /posts`
- `PUT /posts/{post_id}`
- `DELETE /posts/{post_id}`
- `PUT /posts/{post_id}/ebay-draft`
- `POST /posts/{post_id}/ebay/publish`
- `GET /auth/ebay/authorize`
- `GET /auth/ebay/callback`
- `GET /ebay/listings`
- `GET /images/{object_path}`

When a frontend build exists in `static/`, `/` and `/welcome` serve the UI.

## Local Development

Backend with Mongo-backed posts:

```bash
make dev-server
```

Frontend:

```bash
make frontend-install
make frontend-dev
```

Useful URLs:

- API: `http://127.0.0.1:8000`
- Frontend dev server: `http://127.0.0.1:5173`
- MLflow: `http://127.0.0.1:5001`

## Tests

Python tests:

```bash
uv run pytest -q -k "not live and not sandbox"
```

Frontend unit tests:

```bash
cd frontend && npm test
```

Frontend E2E:

```bash
make frontend-e2e
```

Some integration tests require Docker for MongoDB testcontainers. If Docker is not running, those tests are skipped.

## Configuration

Primary backend settings are read from environment variables:

- `POSTS_BACKEND`
- `MONGODB_URI`
- `MONGO_DATABASE`
- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `GCS_IMAGES_BUCKET`
- `FIRESTORE_DATABASE_ID`
- `GEMINI_MODEL`
- `EBAY_APP_ID`
- `EBAY_CERT_ID`
- `EBAY_RUNAME`
- `EBAY_MARKETPLACE_ID`

## Terraform

Infrastructure code lives in `terraform/`.

```bash
make tf-plan
make tf-apply
```
