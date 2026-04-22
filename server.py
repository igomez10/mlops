from __future__ import annotations

# import io
# import torch
# import requests
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import fastapi
from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
from pymongo import MongoClient

from pkg import CloudSettings, FirestoreMongoDatabase, GeminiClient, GoogleCloudStorage
from pkg.posts import InMemoryPostRepository, MongoPostRepository, PostRepository
from pkg.posts.models import Post

# from PIL import Image
# from transformers import pipeline

app_state = {}

# detector = pipeline(
#     task="object-detection",
#     model="hustvl/yolos-base",
#     dtype=torch.float16,
#     device=0,
# )


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    settings = CloudSettings.from_env()
    app_state["cloud_settings"] = settings
    if settings.mongodb_uri:
        mongo_client = MongoClient(settings.mongodb_uri)
        app_state["mongo_client"] = mongo_client
        db_name = os.environ.get("MONGO_DATABASE", "mlops")
        app_state["post_repository"] = MongoPostRepository(
            mongo_client[db_name]["posts"]
        )
    else:
        app_state["post_repository"] = InMemoryPostRepository()
    yield
    mongo = app_state.pop("mongo_client", None)
    app_state.clear()
    if mongo is not None:
        mongo.close()


def get_post_repo() -> PostRepository:
    return app_state["post_repository"]


app = fastapi.FastAPI(lifespan=lifespan)

_default_cors = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5174,http://127.0.0.1:5174"
)
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", _default_cors).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


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
    # Placeholder pricing heuristic (MLflow model loading removed).
    prediction = 200 * inputdata.sqft + 50_000 * inputdata.rooms
    return PredictResponse(prediction=int(prediction))


class CreatePostRequest(BaseModel):
    name: str


class UpdatePostRequest(BaseModel):
    id: str
    name: str


class GetPostRequest(BaseModel):
    id: str | None = None
    name: str | None = None
    include_deleted: bool = False

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> GetPostRequest:
        has_id = self.id is not None
        has_name = self.name is not None
        if has_id == has_name:
            raise ValueError("exactly one of id or name must be provided")
        return self


class ListPostRequest(BaseModel):
    include_deleted: bool = False


class DeletePostRequest(BaseModel):
    id: str


class PostResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    @classmethod
    def from_post(cls, post: Post) -> PostResponse:
        return cls(
            id=post.id,
            name=post.name,
            created_at=post.created_at,
            updated_at=post.updated_at,
            deleted_at=post.deleted_at,
        )


def _parse_list_post_request(include_deleted: bool = False) -> ListPostRequest:
    return ListPostRequest(include_deleted=include_deleted)


@app.post("/posts", response_model=PostResponse, status_code=201)
def http_create_post(
    req: CreatePostRequest,
    repo: Annotated[PostRepository, Depends(get_post_repo)],
) -> PostResponse:
    try:
        post = repo.create(req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PostResponse.from_post(post)


@app.patch("/posts", response_model=PostResponse)
def http_update_post(
    req: UpdatePostRequest,
    repo: Annotated[PostRepository, Depends(get_post_repo)],
) -> PostResponse:
    try:
        post = repo.update(req.id, name=req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(post)


@app.post("/posts/get", response_model=PostResponse)
def http_get_post(
    req: GetPostRequest,
    repo: Annotated[PostRepository, Depends(get_post_repo)],
) -> PostResponse:
    if req.id is not None:
        post = repo.get_by_id(req.id, include_deleted=req.include_deleted)
    else:
        post = repo.get_by_name(req.name or "", include_deleted=req.include_deleted)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(post)


@app.get("/posts", response_model=list[PostResponse])
def http_list_posts(
    req: Annotated[ListPostRequest, Depends(_parse_list_post_request)],
    repo: Annotated[PostRepository, Depends(get_post_repo)],
) -> list[PostResponse]:
    posts = repo.list_posts(include_deleted=req.include_deleted)
    return [PostResponse.from_post(p) for p in posts]


@app.post("/posts/delete", response_model=PostResponse)
def http_soft_delete_post(
    req: DeletePostRequest,
    repo: Annotated[PostRepository, Depends(get_post_repo)],
) -> PostResponse:
    post = repo.soft_delete(req.id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(post)


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
