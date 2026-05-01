from __future__ import annotations

# import io
# import torch
# import requests
import logging
import mimetypes
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import fastapi
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from pymongo import MongoClient
from starlette.requests import Request

from pkg import CloudSettings, FirestoreMongoDatabase, GoogleCloudStorage

# Load .env files so local runs of `uvicorn server:app` pick up the same
# config the rest of the team uses. Root .env carries GCS/Mongo settings;
# product_analyzer/.env carries Gemini + MLflow. Existing process env wins,
# so deployed environments (Cloud Run, CI) are unaffected.
load_dotenv(dotenv_path=".env")
load_dotenv(dotenv_path="product_analyzer/.env")

from pkg.gcs import api_absolute_url_for_object_key, normalize_stored_to_object_key
from pkg.posts import InMemoryPostRepository, MongoPostRepository, Post, PostRepository
from product_analyzer.service import analyze_product_image_bytes

# from PIL import Image
# from transformers import pipeline

app_state: dict[str, Any] = {}
log = logging.getLogger(__name__)


_SEED_POSTS = [
    {
        "name": "Vintage Leather Jacket",
        "description": (
            "Brown leather jacket from the 80s, size M. Minor scuffs on the sleeves, otherwise great condition."
        ),
    },
    {
        "name": "Trek Mountain Bike 2019",
        "description": "Trek Marlin 5 in excellent condition. 29-inch wheels, recently tuned, new brake pads.",
    },
    {
        "name": "Standing Desk — Uplift V2",
        "description": "Electric sit/stand desk, 60x30 walnut top. Includes cable management tray and memory handset.",
    },
    {
        "name": "Sony WH-1000XM4 Headphones",
        "description": "Noise-cancelling over-ear headphones, barely used. Comes with original case and cables.",
    },
    {
        "name": "Mid-Century Coffee Table",
        "description": (
            "Solid walnut with tapered legs, 48x24 inches. Light surface scratches, sturdy and ready to use."
        ),
    },
]


def _seed_posts(repo: "InMemoryPostRepository") -> None:
    for p in _SEED_POSTS:
        try:
            repo.create(p["name"], description=p["description"])
        except ValueError:
            pass


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
    backend = _resolve_posts_backend(settings)
    if backend == "mongodb":
        if not settings.mongodb_uri:
            raise RuntimeError("POSTS_BACKEND=mongodb requires MONGODB_URI")
        mongo_client: MongoClient[Any] = MongoClient(settings.mongodb_uri)
        app_state["mongo_client"] = mongo_client
        db_name = os.environ.get("MONGO_DATABASE", "mlops")
        app_state["post_repository"] = MongoPostRepository(mongo_client[db_name]["posts"])
    elif backend == "firestore":
        db = FirestoreMongoDatabase.from_settings(settings)
        app_state["post_repository"] = MongoPostRepository(db.collection("posts"))
    else:
        repo = InMemoryPostRepository()
        if os.environ.get("SEED_POSTS") == "1":
            _seed_posts(repo)
        app_state["post_repository"] = repo
    if settings.gcs_images_bucket:
        app_state["images_storage"] = GoogleCloudStorage(
            settings.gcs_images_bucket,
        )
    else:
        app_state["images_storage"] = None
    yield
    mongo = app_state.pop("mongo_client", None)
    app_state.clear()
    if mongo is not None:
        mongo.close()


def _resolve_posts_backend(settings: CloudSettings) -> str:
    backend = settings.posts_backend
    if backend in {"memory", "mongodb", "firestore"}:
        return backend
    if backend != "auto":
        raise RuntimeError(f"unsupported POSTS_BACKEND {backend!r}; expected auto, memory, mongodb, or firestore")
    if settings.mongodb_uri:
        return "mongodb"
    if os.environ.get("K_SERVICE"):
        return "firestore"
    return "memory"


def get_post_repo() -> PostRepository:
    return app_state["post_repository"]


def get_images_storage() -> GoogleCloudStorage | None:
    return app_state.get("images_storage")


def _images_bucket() -> str | None:
    s = get_images_storage()
    return s.bucket_name if s is not None else None


def _post_has_stored_image(post: Post, object_path: str, bucket: str | None) -> bool:
    for stored in post.image_urls:
        k = normalize_stored_to_object_key(stored, bucket)
        if k == object_path or k.rstrip("/") == object_path.rstrip("/"):
            return True
    return False


app = fastapi.FastAPI(lifespan=lifespan)

_default_cors = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_cors).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

if os.environ.get("E2E_TEST") == "1":

    @app.post("/__e2e__/reset-posts")
    def e2e_reset_posts() -> dict:
        """In-memory only: new repository so Playwright tests start from an empty list."""
        if app_state.get("mongo_client") is not None:
            return {"ok": False, "reason": "not supported with MongoDB"}
        app_state["post_repository"] = InMemoryPostRepository()
        return {"ok": True}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/images/{object_path:path}", response_class=Response)
def http_get_post_image(
    object_path: str,
    repo: PostRepository = Depends(get_post_repo),
    storage: GoogleCloudStorage | None = Depends(get_images_storage),
) -> Response:
    """
    Stream a post image from private GCS. Only objects referenced on an active
    post (and under ``posts/<post_id>/``) are served.
    """
    if storage is None:
        raise HTTPException(status_code=503, detail="image storage not configured")
    if ".." in object_path or not object_path.startswith("posts/"):
        raise HTTPException(status_code=404, detail="not found")
    m = re.match(r"^posts/([^/]+)/[^/]+$", object_path)
    if not m:
        raise HTTPException(status_code=404, detail="not found")
    post_id = m.group(1)
    post = repo.get_by_id(post_id, include_deleted=False)
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    bucket = storage.bucket_name
    if not _post_has_stored_image(post, object_path, bucket):
        raise HTTPException(status_code=404, detail="not found")
    if not storage.exists(object_path):
        raise HTTPException(status_code=404, detail="not found")
    data = storage.download_bytes(object_path)
    media_type, _ = mimetypes.guess_type(object_path)
    if not media_type:
        media_type = "application/octet-stream"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


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
    num1 = int(request["num1"])
    num2 = int(request["num2"])

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


class UpdatePostRequest(BaseModel):
    name: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdatePostRequest":
        if self.name is None and self.description is None:
            raise ValueError("at least one of name or description is required")
        return self


class ListingResponse(BaseModel):
    id: str
    marketplace_url: str
    image_url: str
    created_at: datetime
    status: str
    description: str


class PostResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    description: str = ""
    deleted_at: datetime | None = None
    listings: list[ListingResponse] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    analysis: dict | None = None

    @classmethod
    def from_post(
        cls,
        post: Post,
        *,
        public_base: str,
        images_bucket: str | None = None,
    ) -> "PostResponse":
        def _img_url(stored: str) -> str:
            key = normalize_stored_to_object_key(stored, images_bucket)
            return api_absolute_url_for_object_key(public_base, key)

        return cls(
            id=post.id,
            name=post.name,
            created_at=post.created_at,
            updated_at=post.updated_at,
            description=post.description,
            deleted_at=post.deleted_at,
            listings=[
                ListingResponse(
                    id=L.id,
                    marketplace_url=L.marketplace_url,
                    image_url=_img_url(L.image_url),
                    created_at=L.created_at,
                    status=L.status,
                    description=L.description,
                )
                for L in post.listings
            ],
            image_urls=[_img_url(u) for u in post.image_urls],
            analysis=post.analysis,
        )


_POST_IMAGE_TYPES = frozenset(
    ("image/jpeg", "image/png", "image/webp", "image/gif"),
)
_MAX_IMAGE_BYTES = 12 * 1024 * 1024
_MAX_IMAGE_FILES = 24


_ANALYZER_SUPPORTED_TYPES = frozenset(("image/jpeg", "image/png"))


async def _upload_image_files_to_gcs(
    post_id: str, uploads: list[UploadFile], storage: GoogleCloudStorage
) -> tuple[list[str], tuple[bytes, str] | None]:
    """Upload images to private GCS.

    Returns ``(object_keys, first_supported)`` where ``first_supported`` is the
    bytes + MIME of the first JPEG/PNG upload (or ``None``) so the caller can
    pass it to the product analyzer without re-reading the form.
    """
    object_keys: list[str] = []
    first_supported: tuple[bytes, str] | None = None
    for upload in uploads:
        data = await upload.read()
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="empty file")
        if len(data) > _MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="file too large")
        ct = (upload.content_type or "").split(";")[0].strip()
        if ct not in _POST_IMAGE_TYPES and upload.filename:
            guess, _ = mimetypes.guess_type(upload.filename)
            if guess in _POST_IMAGE_TYPES:
                ct = guess
        if ct not in _POST_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="only image/jpeg, image/png, image/webp, image/gif allowed",
            )
        ext = mimetypes.guess_extension(ct) or ".img"
        if ext in (".jpe",):
            ext = ".jpg"
        object_name = f"posts/{post_id}/{uuid.uuid4().hex}{ext}"
        storage.upload_bytes(object_name, data, content_type=ct or "application/octet-stream")
        object_keys.append(object_name)
        if first_supported is None and ct in _ANALYZER_SUPPORTED_TYPES:
            first_supported = (data, ct)
    return object_keys, first_supported


@app.get("/posts", response_model=list[PostResponse] | PostResponse)
def http_get_posts(
    request: Request,
    name: str | None = None,
    include_deleted: bool = False,
    repo: PostRepository = Depends(get_post_repo),
) -> list[PostResponse] | PostResponse:
    base = str(request.base_url)
    bkt = _images_bucket()
    if name is not None:
        post = repo.get_by_name(name, include_deleted=include_deleted)
        if post is None:
            raise HTTPException(status_code=404, detail="post not found")
        return PostResponse.from_post(post, public_base=base, images_bucket=bkt)
    posts = repo.list_posts(include_deleted=include_deleted)
    return [PostResponse.from_post(p, public_base=base, images_bucket=bkt) for p in posts]


@app.get("/posts/{post_id}", response_model=PostResponse)
def http_get_post(
    request: Request,
    post_id: str,
    include_deleted: bool = False,
    repo: PostRepository = Depends(get_post_repo),
) -> PostResponse:
    post = repo.get_by_id(post_id, include_deleted=include_deleted)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(
        post,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


@app.post("/posts", response_model=PostResponse, status_code=201)
async def http_create_post(
    request: Request,
    repo: PostRepository = Depends(get_post_repo),
) -> PostResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            raw = await request.json()
        except Exception as e:
            raise HTTPException(status_code=422, detail="invalid JSON body") from e
        if not isinstance(raw, dict):
            raise HTTPException(status_code=422, detail="expected a JSON object")
        name = raw.get("name")
        if not isinstance(name, str):
            raise HTTPException(status_code=422, detail="name is required")
        desc_raw = raw.get("description", "")
        description = desc_raw if isinstance(desc_raw, str) else ""
        try:
            post = repo.create(name, description=description)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return PostResponse.from_post(
            post,
            public_base=str(request.base_url),
            images_bucket=_images_bucket(),
        )

    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json or multipart/form-data",
        )
    form = await request.form()
    body_desc = form.get("description")
    if not isinstance(body_desc, str) or not body_desc.strip():
        raise HTTPException(
            status_code=422,
            detail="description is required (non-empty) for image upload",
        )
    file_uploads: list[UploadFile] = []
    for k, v in form.multi_items():
        if k == "files" and not isinstance(v, str):
            file_uploads.append(cast(UploadFile, v))
    if not file_uploads:
        raise HTTPException(status_code=422, detail="at least one image file is required")

    storage = get_images_storage()
    if storage is None:
        raise HTTPException(
            status_code=503,
            detail="image uploads not configured (set GCS_IMAGES_BUCKET)",
        )
    if len(file_uploads) > _MAX_IMAGE_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"at most {_MAX_IMAGE_FILES} files per request",
        )
    # Upload to bucket first, then persist post with the same id used for object paths
    post_id = str(uuid.uuid4())
    urls, first_supported = await _upload_image_files_to_gcs(post_id, file_uploads, storage)
    # Best-effort product analysis on the first JPEG/PNG. Failures must never
    # block post creation — log and proceed with analysis=None.
    analysis_result: dict | None = None
    if first_supported is not None:
        image_bytes, image_mime = first_supported
        try:
            parsed = await analyze_product_image_bytes(image_bytes, image_mime)
            analysis_result = parsed.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            log.warning("product analysis skipped for post %s: %s", post_id, exc)
    internal_name = f"p-{post_id.replace('-', '')[:16]}"
    try:
        post = repo.create(
            internal_name,
            description=body_desc.strip(),
            post_id=post_id,
            image_urls=urls,
            analysis=analysis_result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PostResponse.from_post(
        post,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


@app.put("/posts/{post_id}", response_model=PostResponse)
def http_update_post(
    request: Request,
    post_id: str,
    req: UpdatePostRequest,
    repo: PostRepository = Depends(get_post_repo),
) -> PostResponse:
    try:
        post = repo.update(
            post_id,
            name=req.name,
            description=req.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(
        post,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


@app.delete("/posts/{post_id}", response_model=PostResponse)
def http_delete_post(
    request: Request,
    post_id: str,
    repo: PostRepository = Depends(get_post_repo),
) -> PostResponse:
    post = repo.soft_delete(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(
        post,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


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
    return {"message": f"Posts created successfully for user {req.user_id} on {req.platform}."}


@app.get("/get_posts")
def get_posts():
    return database


def _configure_static_ui() -> None:
    """After production Docker build, ``static/index.html`` exists. Otherwise JSON welcome at ``/``."""
    static_root = Path(os.environ.get("STATIC_DIR", str(Path(__file__).resolve().parent / "static")))
    if (static_root / "index.html").is_file():
        app.mount(
            "/",
            StaticFiles(directory=str(static_root), html=True),
            name="static",
        )
    else:

        @app.get("/")
        def root() -> dict:
            return {"message": "Welcome to mlops fastapi!"}


_configure_static_ui()


def main() -> None:
    print("Hello from mlops!")


if __name__ == "__main__":
    main()
