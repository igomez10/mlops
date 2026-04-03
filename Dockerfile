# Use an official Python base image
FROM python:3.9-slim

# Set environment variables
ENV MLFLOW_HOME=/mlflow
WORKDIR $MLFLOW_HOME

# Install MLflow and any extra dependencies you may need
RUN pip install --no-cache-dir mlflow

# Expose the default MLflow port
EXPOSE 5000

# Default command: start the MLflow tracking server
CMD ["mlflow", "server", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--default-artifact-root", "/mlflow/artifacts", \
     "--backend-store-uri", "sqlite:///mlflow.db"]