# Submission Milestone 2


## Deploying ML Model as a Web Service

1. GitHub repository
○  Link to your full repo, including all your code, Dockerfile, etc.  
https://github.com/igomez10/mlops

FastAPI Dockerfile: https://github.com/igomez10/mlops/blob/main/Dockerfile.fastapi

MLFlow Dockerfile: We pulled and pushed the official image, so no custom Dockerfile is needed. See Makefile for details: `make push-mlflow`.

○  Direct link(s) to the file(s) where endpoints are defined 

The FastAPI endpoints are defined in `server.py`:

2.  Docker image proof 
○  Screenshot showing your published image in the registry 

<!-- /Users/ignacio/mlops/submission2/proof_image_fastapi.png -->

image proof fastapi.png:
![image proof](proof_image_fastapi.png)

image proof mlflow.png:
![image proof](proof_image_mlflow.png)

○  Image name must match what is used in your code 
3.  Run instructions (important for grading)  In your repo README, include: 
○  How to run the API locally (without Docker, if possible) 
○  How to build and run the Docker container 
