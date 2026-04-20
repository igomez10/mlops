# import io
# import torch
# import requests
import os
from contextlib import asynccontextmanager

import fastapi
import mlflow
import mlflow.pyfunc
import pandas as pd

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


@app.post("/predict_price_sqft")
def predict(inputdata: PredictRequest) -> PredictResponse:
    data = pd.DataFrame([{"sqft": inputdata.sqft, "rooms": inputdata.rooms}])
    result = app_state["model"].predict(data)
    return PredictResponse(prediction=int(result[0]))


class CreatePostsRequest(BaseModel):
    images: list[bytes]
    user_id: int
    dry_run: bool = False
    platform: str | None = "ebay"
    user_estimated_price: int | None = None

    def validate_request(self) -> bool:
        if not self.platform:
            raise ValueError("Missing required field: platform")
        if self.platform not in ["ebay", "craigslist"]:
            raise ValueError(f"Invalid platform: {self.platform}")
        if self.user_estimated_price is not None and self.user_estimated_price < 0:
            raise ValueError("Estimated price must be non-negative.")
        return True

database = []

@app.post("/create_posts")
def create_posts(req: CreatePostsRequest) -> dict:
    try:
        req.validate_request()
    except ValueError as e:
        return {"error": str(e)}
    # TODO 1 Upload assets to storage bucket
    # TODO 2 create new entry in database referencing link in bucket
    # TODO 3 call llm provider with image + prompt
    # TODO 4 update db with generated fields
    # TODO 5 Call Ebay endpoint
    database.append(req)
    # Here you would add logic to process the images and create posts on the specified platform.
    # For this example, we'll just return a success message.
    return {
        "message": f"Posts created successfully for user {req.user_id} on {req.platform}."
    }

@app.get("/get_posts")
def get_posts():
    return database

def main() -> None:
    print("Hello from mlops!")


if __name__ == "__main__":
    main()
