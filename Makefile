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

GCP_REGION := us-central1
GCP_PROJECT := mlops-492103
# Post image uploads (terraform: ${project_id}-mlops-images)
DEV_GCS_IMAGES_BUCKET := $(GCP_PROJECT)-mlops-images
VERTEX_ENDPOINT := linear-regression-endpoint
VERTEX_ARTIFACT_URI := gs://$(GCP_PROJECT)-mlflow-artifacts/models/linear-regression/
SKLEARN_IMAGE := us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-3:latest
AR_IMAGE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/mlflow/mlflow:v3.10.1-full
FASTAPI_IMAGE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/fastapi/fastapi:latest
MLFLOW_VERSION := v3.10.1-full

.PHONY: build run stop clean tf-plan tf-apply gcp-build-ui push-mlflow push-fastapi redeploy-mlflow redeploy-fastapi run-fastapi compose-up-dev dev-server start-docker-compose frontend-install frontend-dev ui frontend-e2e vertex-upload-toy-model vertex-deploy-toy-model vertex-undeploy-toy-model

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

# Build & deploy UI to Cloud Run (requires gcloud, cloudbuild.yaml, and existing "fastapi" service)
gcp-build-ui:
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

redeploy-fastapi:
	gcloud run deploy fastapi \
		--image $(FASTAPI_IMAGE) \
		--cpu-throttling \
		--region $(GCP_REGION) \
		--project $(GCP_PROJECT) \
		--quiet

run-fastapi:
	uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Start MLflow + MongoDB for local dev (host uses localhost URLs, not Docker service names).
compose-up-dev:
	DEV_MLFLOW_PORT=$(DEV_MLFLOW_PORT) DEV_MONGO_PORT=$(DEV_MONGO_PORT) $(COMPOSE) up -d mlflow mongodb

# Dev: reload on code changes; copy stdout/stderr to SERVER_LOG (default ./logs/server.log).
dev-server: compose-up-dev
	mkdir -p $$(dirname $(SERVER_LOG))
	MLFLOW_TRACKING_URI=$(DEV_MLFLOW_URL) \
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
