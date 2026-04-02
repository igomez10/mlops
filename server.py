# import io
# import torch
# import requests
import fastapi

# from PIL import Image
from pydantic import BaseModel

# from transformers import pipeline

app = fastapi.FastAPI()

# detector = pipeline(
#     task="object-detection",
#     model="hustvl/yolos-base",
#     dtype=torch.float16,
#     device=0,
# )


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


# add with body parameters
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
    # Define your input data structure here
    num1: int
    num2: int


class PredictResponse(BaseModel):
    # Define your output data structure here
    prediction: str


@app.post("/predict")
def predict(inputdata: PredictRequest) -> PredictResponse:
    # Dummy prediction logic
    b0 = 27
    b1 = 256
    b2 = 339
    prediction = b0 + b1 * inputdata.num1 + b2 * inputdata.num2
    return PredictResponse(prediction=str(prediction))


def main() -> None:
    print("Hello from mlops!")


if __name__ == "__main__":
    main()
