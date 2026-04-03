# import io
# import torch
# import requests
import os
from contextlib import asynccontextmanager

import mlflow
import mlflow.pyfunc
import pandas as pd
import fastapi

# from PIL import Image
# from transformers import pipeline
from pydantic import BaseModel

app_state = {}

# detector = pipeline(
#     task="object-detection",
#     model="hustvl/yolos-base",
#     dtype=torch.float16,
#     device=0,
# )


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    model_uri = os.environ.get(
        "MLFLOW_MODEL_URI",
        f"models:/{os.environ.get('MLFLOW_MODEL_NAME', 'model')}/latest",
    )
    app_state["model"] = mlflow.pyfunc.load_model(model_uri)
    yield
    app_state.clear()


app = fastapi.FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def hello() -> dict:
    return {"message": "Welcome to mlops fastapi!"}


@app.get("/usfca")
def usfca() -> str:
    print("someone requested the usfca endpoint")
    return "something"


@app.post("/add_query_parameters")
def addWithQueryParameters(num1: int, num2: int) -> dict:
    result = num1 + num2
    return {"result": result}


@app.post("/add_body_parameters")
def addWithBodyParameters(request: dict) -> dict:
    num1 = int(request.get("num1"))
    num2 = int(request.get("num2"))

    b0 = 27
    b1 = 256
    b2 = 339
    prediction = b0 + b1 * num1 + b2 * num2

    return {"result": prediction}


# class YoloRequest(BaseModel):
#     image_url: str


# @app.post("/yolo")
# def yolo(request: YoloRequest) -> list:
#     response = requests.get(request.image_url, timeout=10)
#     response.raise_for_status()
#     image = Image.open(io.BytesIO(response.content)).convert("RGB")
#     return detector(image)


class PredictRequest(BaseModel):
    sqft: int
    rooms: int


class PredictResponse(BaseModel):
    prediction: int


@app.post("/predict")
def predict(inputdata: PredictRequest) -> PredictResponse:
    data = pd.DataFrame([{"sqft": inputdata.sqft, "rooms": inputdata.rooms}])
    result = app_state["model"].predict(data)
    return PredictResponse(prediction=int(result[0]))


def main() -> None:
    print("Hello from mlops!")


if __name__ == "__main__":
    main()
