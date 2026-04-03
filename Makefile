IMAGE_NAME := mlflow-server
CONTAINER_NAME := mlflow
VOLUME_NAME := mlflow-data
PORT := 5001

.PHONY: build run stop clean

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
