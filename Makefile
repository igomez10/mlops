IMAGE_NAME := mlflow-server
CONTAINER_NAME := mlflow
VOLUME_NAME := mlflow-data
PORT := 5001

GCP_REGION := us-central1
GCP_PROJECT := mlops-492103
AR_IMAGE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/mlflow/mlflow:v3.10.1-full

.PHONY: build run stop clean tf-plan tf-apply push-mlflow redeploy

build:
	docker build -t $(IMAGE_NAME) .

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

MLFLOW_VERSION := v3.10.1-full

push-mlflow:
	docker pull --platform linux/amd64 ghcr.io/mlflow/mlflow:$(MLFLOW_VERSION)
	docker tag ghcr.io/mlflow/mlflow:$(MLFLOW_VERSION) $(AR_IMAGE)
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --quiet
	docker push $(AR_IMAGE)

redeploy:
	gcloud run deploy mlflow \
		--image $(AR_IMAGE) \
		--region $(GCP_REGION) \
		--project $(GCP_PROJECT) \
		--quiet
