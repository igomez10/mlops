IMAGE_NAME := mlflow-server
CONTAINER_NAME := mlflow
VOLUME_NAME := mlflow-data
PORT := 5001

SERVER_LOG := ./logs/server.log
DEV_HOST := 0.0.0.0
DEV_PORT := 8000
# Published host ports — must match docker-compose.yml ${DEV_*_PORT:-defaults}
DEV_MLFLOW_PORT := 5001
DEV_MONGO_PORT := 27017
DEV_MLFLOW_URL := http://127.0.0.1:$(DEV_MLFLOW_PORT)
DEV_MONGODB_URL := mongodb://127.0.0.1:$(DEV_MONGO_PORT)

COMPOSE := docker compose
LOAD_DOTENV = if [ -f .env ]; then set -a; . ./.env; set +a; fi;

GCP_REGION := us-central1
GCP_PROJECT := mlops-492103
# Post image uploads (terraform: ${project_id}-mlops-images)
DEV_GCS_IMAGES_BUCKET := $(GCP_PROJECT)-mlops-images
VERTEX_ENDPOINT := linear-regression-endpoint
VERTEX_ARTIFACT_URI := gs://$(GCP_PROJECT)-mlflow-artifacts/models/linear-regression/
SKLEARN_IMAGE := us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-3:latest
AR_IMAGE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/mlflow/mlflow:v3.10.1-full
FASTAPI_IMAGE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/fastapi/fastapi:latest
FASTAPI_DEV_IMAGE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/fastapi/fastapi-ignacio:latest
MLFLOW_VERSION := v3.10.1-full

.PHONY: build run stop clean tf-plan tf-apply gcp-build-app push-mlflow push-fastapi push-fastapi-dev redeploy-mlflow redeploy-fastapi redeploy-fastapi-dev deploy-fastapi-local deploy-fastapi-dev-local run-fastapi run-fastapi-firestore compose-up-dev dev-server dev-server-mongo start-docker-compose frontend-install frontend-dev ui frontend-e2e lint test clear-posts clear-posts-firestore completion-zsh vertex-upload-toy-model vertex-deploy-toy-model vertex-undeploy-toy-model

build-fastapi:
	docker build -t $(FASTAPI_IMAGE) -f Dockerfile.fastapi .

run:
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):5000 \
		-v $(VOLUME_NAME):/mlflow \
		$(IMAGE_NAME) \
		mlflow server \
			--host 0.0.0.0 \
			--port 5000 \
			--default-artifact-root /mlflow/artifacts \
			--serve-artifacts

stop:
	docker stop $(CONTAINER_NAME) && docker rm $(CONTAINER_NAME)

clean: stop
	docker volume rm $(VOLUME_NAME)

tf-plan:
	cd terraform && terraform plan

tf-apply:
	cd terraform && terraform apply -auto-approve

# Build & deploy combined FastAPI + static UI to Cloud Run (gcloud, cloudbuild.yaml)
gcp-build-app:
	gcloud builds submit --config=cloudbuild.yaml --project $(GCP_PROJECT)


push-mlflow:
	docker pull --platform linux/amd64 ghcr.io/mlflow/mlflow:$(MLFLOW_VERSION)
	docker tag ghcr.io/mlflow/mlflow:$(MLFLOW_VERSION) $(AR_IMAGE)
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --quiet
	docker push $(AR_IMAGE)

redeploy-mlflow:
	gcloud run deploy mlflow \
		--image $(AR_IMAGE) \
		--cpu-throttling \
		--region $(GCP_REGION) \
		--project $(GCP_PROJECT) \
		--quiet

push-fastapi:
	docker build --platform linux/amd64 -t $(FASTAPI_IMAGE) -f Dockerfile.fastapi .
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --quiet
	docker push $(FASTAPI_IMAGE)

push-fastapi-dev:
	docker build --platform linux/amd64 -t $(FASTAPI_DEV_IMAGE) -f Dockerfile.fastapi .
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --quiet
	docker push $(FASTAPI_DEV_IMAGE)

redeploy-fastapi:
	gcloud run deploy fastapi \
		--image $(FASTAPI_IMAGE) \
		--cpu-throttling \
		--region $(GCP_REGION) \
		--project $(GCP_PROJECT) \
		--quiet

redeploy-fastapi-dev:
	gcloud run deploy fastapi-dev \
		--image $(FASTAPI_DEV_IMAGE) \
		--cpu-throttling \
		--region $(GCP_REGION) \
		--project $(GCP_PROJECT) \
		--quiet

deploy-fastapi-local: push-fastapi redeploy-fastapi

deploy-fastapi-dev-local: push-fastapi-dev redeploy-fastapi-dev

run-fastapi:
	$(LOAD_DOTENV) \
	GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) \
	GCS_IMAGES_BUCKET=$(DEV_GCS_IMAGES_BUCKET) \
	POSTS_BACKEND=mongodb \
	MONGODB_URI=$(DEV_MONGODB_URL) \
	uvicorn server:app --host 0.0.0.0 --port 8000 --reload

run-fastapi-firestore:
	$(LOAD_DOTENV) \
	GCS_IMAGES_BUCKET=$(DEV_GCS_IMAGES_BUCKET) \
	GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) \
	POSTS_BACKEND=firestore \
	FIRESTORE_DATABASE_ID='(default)' \
	uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Start MLflow + MongoDB for local dev (host uses localhost URLs, not Docker service names).
compose-up-dev:
	DEV_MLFLOW_PORT=$(DEV_MLFLOW_PORT) DEV_MONGO_PORT=$(DEV_MONGO_PORT) $(COMPOSE) up -d mlflow mongodb

# Dev: reload on code changes; local MongoDB-backed posts.
dev-server: compose-up-dev
	mkdir -p $$(dirname $(SERVER_LOG))
	$(LOAD_DOTENV) \
	GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) \
	GCS_IMAGES_BUCKET=$(DEV_GCS_IMAGES_BUCKET) \
	POSTS_BACKEND=mongodb \
	MONGODB_URI=$(DEV_MONGODB_URL) \
	SEED_POSTS=1 \
	uvicorn server:app --host $(DEV_HOST) --port $(DEV_PORT) --reload 2>&1 | tee $(SERVER_LOG)

# Dev: same as dev-server but backed by MongoDB (starts Docker Compose services first).
dev-server-mongo: compose-up-dev
	mkdir -p $$(dirname $(SERVER_LOG))
	$(LOAD_DOTENV) \
	GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) \
	MLFLOW_TRACKING_URI=$(DEV_MLFLOW_URL) \
	POSTS_BACKEND=mongodb \
	MONGODB_URI=$(DEV_MONGODB_URL) \
	GCS_IMAGES_BUCKET=$(DEV_GCS_IMAGES_BUCKET) \
	uvicorn server:app --host $(DEV_HOST) --port $(DEV_PORT) --reload 2>&1 | tee $(SERVER_LOG)

start-docker-compose:
	DEV_MLFLOW_PORT=$(DEV_MLFLOW_PORT) DEV_MONGO_PORT=$(DEV_MONGO_PORT) $(COMPOSE) up -d

frontend-install:
	cd frontend && npm ci

frontend-dev:
	cd frontend && npm run dev

# React UI (Vite dev server; use with API e.g. make dev-server on :8000).
ui: frontend-dev

# Playwright starts API (in-memory Mongo) + Vite on ports 9876 / 5174 (see frontend/e2e/ports.ts).
frontend-e2e:
	cd frontend && CI=1 npm run test:e2e

test:
	$(LOAD_DOTENV) \
	GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) \
	uv run pytest tests/ -q -k "not live and not sandbox"

clear-posts:
	mongosh $(DEV_MONGODB_URL)/mlops --eval 'db.posts.deleteMany({})'

clear-posts-firestore:
	$(LOAD_DOTENV) \
	GOOGLE_CLOUD_PROJECT=$(GCP_PROJECT) \
	uv run python3 -c "\
import os; \
from google.cloud import firestore; \
db = firestore.Client(project=os.environ['GOOGLE_CLOUD_PROJECT'], database=os.environ.get('FIRESTORE_DATABASE_ID','(default)')); \
coll = db.collection('posts'); \
deleted = sum(1 for doc in coll.stream() if (doc.reference.delete() or True)); \
print(f'Deleted {deleted} posts')"

lint:
	uv sync --frozen --group dev
	uv run ruff check .
	uv run mypy pkg/ server.py

completion-zsh:
	mkdir -p scripts/completion
	uv run register-python-argcomplete --shell zsh ebay-cli > scripts/completion/_ebay-cli

vertex-upload-toy-model:
	gcloud ai models upload \
		--region=$(GCP_REGION) \
		--display-name=toy-linear-regression \
		--artifact-uri=$(VERTEX_ARTIFACT_URI) \
		--container-image-uri=$(SKLEARN_IMAGE)

vertex-undeploy-toy-model:
	DEPLOYED_MODEL_ID=$$(gcloud ai endpoints describe $(VERTEX_ENDPOINT) \
		--region=$(GCP_REGION) \
		--format="value(deployedModels[0].id)") && \
	gcloud ai endpoints undeploy-model $(VERTEX_ENDPOINT) \
		--region=$(GCP_REGION) \
		--deployed-model-id=$$DEPLOYED_MODEL_ID

vertex-deploy-toy-model:
	MODEL_ID=$$(gcloud ai models upload \
		--region=$(GCP_REGION) \
		--display-name=toy-linear-regression \
		--artifact-uri=$(VERTEX_ARTIFACT_URI) \
		--container-image-uri=$(SKLEARN_IMAGE) \
		--format="value(model)") && \
	gcloud ai endpoints deploy-model $(VERTEX_ENDPOINT) \
		--region=$(GCP_REGION) \
		--model=$$MODEL_ID \
		--display-name=toy-linear-regression \
		--machine-type=n1-standard-2 \
		--min-replica-count=1 \
		--max-replica-count=1
