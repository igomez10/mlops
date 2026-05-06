from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import mimetypes
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import fastapi
from fastapi import Depends, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from pymongo import MongoClient
from starlette.requests import Request

# Load .env files so local runs of `uvicorn server:app` pick up the same
# config the rest of the team uses. Root .env carries GCS/Mongo settings;
# product_analyzer/.env carries Gemini + MLflow. Existing process env wins,
# so deployed environments (Cloud Run, CI) are unaffected.
# load_dotenv(dotenv_path=".env")
# load_dotenv(dotenv_path="product_analyzer/.env")
from pkg import (
    CloudSettings,
    EbayTokenRepository,
    EbayUserToken,
    FirestoreMongoDatabase,
    GoogleCloudStorage,
    InMemoryEbayTokenRepository,
    MongoEbayTokenRepository,
)
from pkg.ebay import DEFAULT_USER_SCOPES, EbayClient
from pkg.ebay_listing_prefill import EbayDraftPrefillService
from pkg.gcs import api_absolute_url_for_object_key, normalize_stored_to_object_key  # noqa: E402
from pkg.gemini import GeminiClient
from pkg.logging_context import (
    REQUEST_ID_HEADER,
    configure_logging,
    get_logger,
    get_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from pkg.posts import InMemoryPostRepository, Listing, MongoPostRepository, Post, PostRepository  # noqa: E402
from product_analyzer import ProductAnalyzer  # noqa: E402

# from PIL import Image
# from transformers import pipeline

configure_logging()

app_state: dict[str, Any] = {}
log = get_logger(__name__)
logger = log
_raw_logger = logging.getLogger(__name__)


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
    app_state["ebay_client"] = (
        EbayClient.from_settings(settings) if settings.ebay_app_id and settings.ebay_cert_id else None
    )
    backend = _resolve_posts_backend(settings)
    if backend == "mongodb":
        if not settings.mongodb_uri:
            raise RuntimeError("POSTS_BACKEND=mongodb requires MONGODB_URI")
        mongo_client: MongoClient[Any] = MongoClient(settings.mongodb_uri)
        app_state["mongo_client"] = mongo_client
        db_name = os.environ.get("MONGO_DATABASE", "mlops")
        app_state["post_repository"] = MongoPostRepository(mongo_client[db_name]["posts"])
        app_state["ebay_token_repository"] = MongoEbayTokenRepository(mongo_client[db_name]["ebay_user_tokens"])
    elif backend == "firestore":
        db = FirestoreMongoDatabase.from_settings(settings)
        app_state["post_repository"] = MongoPostRepository(db.collection("posts"))
        app_state["ebay_token_repository"] = MongoEbayTokenRepository(db.collection("ebay_user_tokens"))
    else:
        repo = InMemoryPostRepository()
        if os.environ.get("SEED_POSTS") == "1":
            _seed_posts(repo)
        app_state["post_repository"] = repo
        app_state["ebay_token_repository"] = InMemoryEbayTokenRepository()
    if settings.gcs_images_bucket:
        app_state["images_storage"] = GoogleCloudStorage(
            settings.gcs_images_bucket,
        )
    else:
        app_state["images_storage"] = None
    app_state["product_analyzer"] = ProductAnalyzer()
    yield
    mongo = app_state.pop("mongo_client", None)
    ebay_client = app_state.pop("ebay_client", None)
    app_state.clear()
    if isinstance(ebay_client, EbayClient):
        ebay_client.close()
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


def get_ebay_token_repo() -> EbayTokenRepository:
    return app_state["ebay_token_repository"]


def get_images_storage() -> GoogleCloudStorage | None:
    return app_state.get("images_storage")


def _get_ebay_client(settings: CloudSettings) -> EbayClient:
    client = app_state.get("ebay_client")
    if client is not None:
        return client
    return EbayClient.from_settings(settings)


def _ebay_state_secret(settings: CloudSettings) -> str:
    if not settings.ebay_cert_id:
        raise RuntimeError("EBAY_CERT_ID must be configured")
    return settings.ebay_cert_id


def _make_ebay_state(user_id: str, settings: CloudSettings) -> str:
    log.info("controller._make_ebay_state user_id=%s", user_id)
    payload = {
        "user_id": user_id,
        "nonce": uuid.uuid4().hex,
    }
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(
        _ebay_state_secret(settings).encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def _parse_ebay_state(state: str, settings: CloudSettings) -> str:
    log.info("controller._parse_ebay_state")
    try:
        encoded_payload, signature = state.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid ebay state") from exc
    padding = "=" * (-len(encoded_payload) % 4)
    expected = hmac.new(
        _ebay_state_secret(settings).encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=400, detail="invalid ebay state")
    try:
        payload = json.loads(base64.urlsafe_b64decode(f"{encoded_payload}{padding}"))
        user_id = str(payload["user_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid ebay state") from exc
    return user_id


def get_product_analyzer() -> ProductAnalyzer:
    return app_state["product_analyzer"]


def _images_bucket() -> str | None:
    s = get_images_storage()
    return s.bucket_name if s is not None else None


def _post_has_stored_image(post: Post, object_path: str, bucket: str | None) -> bool:
    for stored in post.image_urls:
        k = normalize_stored_to_object_key(stored, bucket)
        if k == object_path or k.rstrip("/") == object_path.rstrip("/"):
            return True
    return False


class EbayAuthorizeResponse(BaseModel):
    authorization_url: str
    state: str
    scopes: list[str]


class EbayCallbackResponse(BaseModel):
    user_id: str
    scopes: list[str]
    expires_at: datetime
    refresh_token_present: bool


class EbayListingSummaryResponse(BaseModel):
    sku: str
    offer_id: str | None = None
    listing_id: str | None = None
    marketplace_id: str | None = None
    format: str | None = None
    available_quantity: int | None = None
    category_id: str | None = None
    merchant_location_key: str | None = None
    listing_description: str | None = None
    status: str | None = None
    price: float | None = None
    currency: str | None = None


class EbayListingsResponse(BaseModel):
    user_id: str
    listings: list[EbayListingSummaryResponse] = Field(default_factory=list)


def _store_ebay_callback(
    *,
    code: str | None,
    state: str | None,
    error: str | None,
    error_description: str | None,
    repo: EbayTokenRepository,
) -> EbayCallbackResponse:
    log.info(
        "controller._store_ebay_callback code_present=%s state_present=%s error_present=%s",
        bool(code),
        bool(state),
        bool(error),
    )
    settings = app_state["cloud_settings"]
    if error:
        detail = error_description or error
        logger.warning(
            "ebay authorization rejected",
            extra={"error": error, "error_description": error_description, "state_present": bool(state)},
        )
        raise HTTPException(status_code=400, detail=f"ebay authorization failed: {detail}")
    if not code or not state:
        logger.warning(
            "ebay callback missing required params",
            extra={"code_present": bool(code), "state_present": bool(state)},
        )
        raise HTTPException(status_code=400, detail="missing ebay code or state")
    if not settings.ebay_runame:
        raise HTTPException(status_code=503, detail="EBAY_RUNAME not configured")

    user_id = _parse_ebay_state(state, settings)
    token_body = _get_ebay_client(settings).exchange_authorization_code(
        code,
        runame=settings.ebay_runame,
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=int(token_body.get("expires_in", 0)))
    raw_refresh_expires = token_body.get("refresh_token_expires_in")
    refresh_expires_at = now + timedelta(seconds=int(raw_refresh_expires)) if raw_refresh_expires is not None else None
    scopes = str(token_body.get("scope") or "").split()
    existing = repo.get_by_user_id(user_id)
    token = EbayUserToken(
        user_id=user_id,
        access_token=str(token_body["access_token"]),
        refresh_token=(str(token_body.get("refresh_token")) if token_body.get("refresh_token") is not None else None),
        token_type=str(token_body.get("token_type") or "Bearer"),
        scopes=scopes,
        expires_at=expires_at,
        refresh_token_expires_at=refresh_expires_at,
        created_at=existing.created_at if existing is not None else now,
        updated_at=now,
    )
    repo.upsert(token)
    logger.info(
        "ebay authorization accepted",
        extra={
            "user_id": user_id,
            "scopes": scopes,
            "refresh_token_present": token.refresh_token is not None,
        },
    )
    return EbayCallbackResponse(
        user_id=user_id,
        scopes=token.scopes,
        expires_at=token.expires_at,
        refresh_token_present=token.refresh_token is not None,
    )


def _get_valid_ebay_user_token(
    user_id: str,
    *,
    repo: EbayTokenRepository,
    client: EbayClient,
) -> EbayUserToken:
    log.info("controller._get_valid_ebay_user_token user_id=%s", user_id)
    token = repo.get_by_user_id(user_id)
    if token is None:
        raise HTTPException(status_code=404, detail="ebay token not found")

    now = datetime.now(timezone.utc)
    if token.expires_at > now:
        return token
    if not token.refresh_token:
        raise HTTPException(status_code=401, detail="ebay token expired")

    token_body = client.refresh_user_access_token(
        token.refresh_token,
        scopes=tuple(token.scopes) if token.scopes else None,
    )
    expires_at = now + timedelta(seconds=int(token_body.get("expires_in", 0)))
    raw_refresh_expires = token_body.get("refresh_token_expires_in")
    refresh_expires_at = (
        now + timedelta(seconds=int(raw_refresh_expires))
        if raw_refresh_expires is not None
        else token.refresh_token_expires_at
    )
    scopes = str(token_body.get("scope") or "").split() or token.scopes
    refreshed = EbayUserToken(
        user_id=token.user_id,
        access_token=str(token_body["access_token"]),
        refresh_token=(
            str(token_body.get("refresh_token")) if token_body.get("refresh_token") is not None else token.refresh_token
        ),
        token_type=str(token_body.get("token_type") or token.token_type or "Bearer"),
        scopes=scopes,
        expires_at=expires_at,
        refresh_token_expires_at=refresh_expires_at,
        created_at=token.created_at or now,
        updated_at=now,
    )
    repo.upsert(refreshed)
    return refreshed


def _resolve_ebay_listing_title(analysis: dict[str, Any], fallback: str) -> str:
    log.info("controller._resolve_ebay_listing_title fallback=%s", fallback)
    return EbayDraftPrefillService._resolve_listing_title(analysis, fallback)


def _resolve_ebay_listing_description(analysis: dict[str, Any], fallback: str) -> str:
    log.info("controller._resolve_ebay_listing_description")
    return EbayDraftPrefillService._resolve_listing_description(analysis, fallback)


def _resolve_ebay_price_and_currency(analysis: dict[str, Any]) -> tuple[float, str]:
    log.info("controller._resolve_ebay_price_and_currency")
    return EbayDraftPrefillService._resolve_price_and_currency(analysis)


def _resolve_ebay_condition(analysis: dict[str, Any]) -> str:
    log.info("controller._resolve_ebay_condition")
    return EbayDraftPrefillService._resolve_condition(analysis)


# Ordered from least to most desirable so we can upgrade when needed.
_CONDITION_UPGRADE_ORDER = [
    "FOR_PARTS_OR_NOT_WORKING",
    "USED_ACCEPTABLE",
    "USED_GOOD",
    "USED_VERY_GOOD",
    "USED_EXCELLENT",
    "SELLER_REFURBISHED",
    "GOOD_REFURBISHED",
    "VERY_GOOD_REFURBISHED",
    "EXCELLENT_REFURBISHED",
    "CERTIFIED_REFURBISHED",
    "NEW_WITH_DEFECTS",
    "NEW_OTHER",
    "LIKE_NEW",
    "NEW",
]


def _pick_condition(desired: str, valid_conditions: list[str]) -> str:
    """Return the closest valid condition to `desired`, upgrading when necessary."""
    log.info("controller._pick_condition desired=%s valid_count=%d", desired, len(valid_conditions))
    return EbayDraftPrefillService._pick_condition(desired, valid_conditions)


def _resolve_ebay_category_id(
    analysis: dict[str, Any], fallback: str, *, client: EbayClient, marketplace_id: str
) -> str:
    log.info("controller._resolve_ebay_category_id fallback=%s marketplace=%s", fallback, marketplace_id)
    query = str(analysis.get("product_name") or "").strip() or fallback
    suggestions = client.get_category_suggestions(query, marketplace_id=marketplace_id)
    if not suggestions:
        raise RuntimeError(f"no eBay category suggestions returned for query {query!r}")
    return suggestions[0].category_id


def _build_public_image_urls(image_urls: list[str], *, public_base: str, images_bucket: str | None) -> list[str]:
    log.info("controller._build_public_image_urls count=%d", len(image_urls))
    return [
        api_absolute_url_for_object_key(public_base, normalize_stored_to_object_key(stored, images_bucket))
        for stored in image_urls
    ]


def _suggest_item_specifics(
    analysis: dict[str, Any],
    aspects: list[dict[str, Any]],
    gemini_client: GeminiClient,
) -> dict[str, list[str]]:
    """Use Gemini to suggest values for the given eBay item aspects."""
    log.info("controller._suggest_item_specifics aspect_count=%d", len(aspects))
    return EbayDraftPrefillService._suggest_missing_item_specifics(
        analysis=analysis,
        product_description="",
        aspects=aspects,
        gemini_client=gemini_client,
    )


def _build_ebay_draft(
    *,
    post: Post,
    analysis: dict[str, Any],
    user_id: str,
    settings: CloudSettings,
) -> dict[str, Any]:
    """Build an eBay listing draft from LLM analysis without making any seller API calls."""
    log.info("controller._build_ebay_draft post_id=%s user_id=%s", post.id, user_id)
    service = EbayDraftPrefillService(
        settings=settings,
        ebay_client=_get_ebay_client(settings),
    )
    return service.build_draft(post=post, analysis=analysis, user_id=user_id)


def _publish_ebay_from_draft(
    *,
    post: Post,
    draft: dict[str, Any],
    public_base: str,
    settings: CloudSettings,
    repo: EbayTokenRepository,
) -> Listing:
    """Create and publish an eBay listing using a stored draft."""
    log.info("controller._publish_ebay_from_draft post_id=%s", post.id)
    user_id = str(draft.get("user_id") or "")
    if not user_id:
        raise ValueError("draft is missing user_id")
    client = _get_ebay_client(settings)
    token = _get_valid_ebay_user_token(user_id, repo=repo, client=client)

    category_id = str(draft.get("category_id") or "")
    title = str(draft.get("title") or "")
    listing_description = str(draft.get("description") or "")
    price_value = float(draft.get("price") or 19.99)
    currency = str(draft.get("currency") or "USD")
    desired_condition = str(draft.get("condition") or "USED_GOOD")
    valid_conditions = client.get_valid_conditions(category_id, marketplace_id=settings.ebay_marketplace_id)
    condition = _pick_condition(desired_condition, valid_conditions)
    item_specifics: dict[str, list[str]] = {
        k: v for k, v in (draft.get("item_specifics") or {}).items() if v and v != [""]
    }

    mid = settings.ebay_marketplace_id
    fulfillment_policies = client.get_fulfillment_policies(token.access_token, marketplace_id=mid)
    payment_policies = client.get_payment_policies(token.access_token, marketplace_id=mid)
    return_policies = client.get_return_policies(token.access_token, marketplace_id=mid)
    if not fulfillment_policies:
        raise RuntimeError("no eBay fulfillment policies available for the authenticated user")
    if not payment_policies:
        raise RuntimeError("no eBay payment policies available for the authenticated user")
    if not return_policies:
        raise RuntimeError("no eBay return policies available for the authenticated user")

    merchant_location_key = settings.ebay_merchant_location_key
    client.create_inventory_location(
        merchant_location_key,
        token.access_token,
        {
            "name": merchant_location_key,
            "merchantLocationStatus": "ENABLED",
            "locationTypes": ["WAREHOUSE"],
            "location": {
                "address": {
                    "city": settings.ebay_location_city,
                    "stateOrProvince": settings.ebay_location_state,
                    "country": settings.ebay_location_country,
                }
            },
        },
    )

    public_images = _build_public_image_urls(post.image_urls, public_base=public_base, images_bucket=_images_bucket())
    sku = f"post-{post.id}"
    product: dict[str, Any] = {"title": title, "description": listing_description, "imageUrls": public_images}
    brand = str((item_specifics.get("Brand") or [""])[0]).strip()
    model = str((item_specifics.get("Model") or [""])[0]).strip()
    if brand:
        product["brand"] = brand
    if model:
        product["mpn"] = model
    if item_specifics:
        product["aspects"] = item_specifics

    client.create_or_replace_inventory_item(
        sku,
        token.access_token,
        {"availability": {"shipToLocationAvailability": {"quantity": 1}}, "condition": condition, "product": product},
    )
    offer_payload: dict[str, Any] = {
        "sku": sku,
        "marketplaceId": settings.ebay_marketplace_id,
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "categoryId": category_id,
        "merchantLocationKey": merchant_location_key,
        "pricingSummary": {"price": {"value": f"{price_value:.2f}", "currency": currency}},
        "listingDescription": listing_description,
        "listingPolicies": {
            "fulfillmentPolicyId": fulfillment_policies[0].policy_id,
            "paymentPolicyId": payment_policies[0].policy_id,
            "returnPolicyId": return_policies[0].policy_id,
        },
    }
    offer_id = client.create_offer(token.access_token, offer_payload)
    publish_body = client.publish_offer(offer_id, token.access_token)
    offer_body = client.get_offer(offer_id, token.access_token)
    listing_id = str(
        publish_body.get("listingId")
        or offer_body.get("listingId")
        or ((offer_body.get("listing") or {}).get("listingId"))
        or offer_id
    )
    ebay_host = "www.sandbox.ebay.com" if client._sandbox else "www.ebay.com"
    marketplace_url = str(publish_body.get("listingWebUrl") or f"https://{ebay_host}/itm/{listing_id}")
    listing_status = str(
        offer_body.get("status")
        or ((offer_body.get("listing") or {}).get("status"))
        or publish_body.get("status")
        or "published"
    )

    # Best-effort: update the published listing description to include a back-link
    # to the originating post in our app, so buyers can find it again.
    post_url = f"{public_base.rstrip('/')}/posts/{post.id}"
    description_with_link = f"{listing_description}\n\n---\nSee the original listing: {post_url}"
    try:
        client.update_offer(
            offer_id,
            token.access_token,
            {**offer_payload, "listingDescription": description_with_link},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("could not back-link post %s on eBay offer %s: %s", post.id, offer_id, exc)

    return Listing(
        id=listing_id,
        marketplace_url=marketplace_url,
        image_url=post.image_urls[0] if post.image_urls else "",
        created_at=datetime.now(timezone.utc),
        status=listing_status,
        description=listing_description,
    )


app = fastapi.FastAPI(lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Bind a request id to the context so every layer's logs can be correlated.

    Honor an inbound ``X-Request-Id`` if present (so upstream proxies and
    front-end retries can carry their own ids); otherwise mint a new one.
    The id is echoed back in the response header for clients/tools to grab.
    """
    incoming = request.headers.get(REQUEST_ID_HEADER)
    request_id = incoming.strip() if incoming and incoming.strip() else new_request_id()
    token = set_request_id(request_id)
    log.info(
        "http.request.start method=%s path=%s client=%s request_id=%s",
        request.method,
        request.url.path,
        request.client.host if request.client else "-",
        request_id,
    )
    try:
        response = await call_next(request)
    except Exception:
        log.exception("http.request.error method=%s path=%s", request.method, request.url.path)
        reset_request_id(token)
        raise
    response.headers[REQUEST_ID_HEADER] = request_id
    log.info(
        "http.request.end method=%s path=%s status=%d",
        request.method,
        request.url.path,
        response.status_code,
    )
    reset_request_id(token)
    return response


_default_cors = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8000,http://127.0.0.1:8000"
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_cors).split(",") if o.strip()]
_allow_all_origins = _cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all_origins else _cors_origins,
    allow_credentials=False if _allow_all_origins else True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

if os.environ.get("E2E_TEST") == "1":

    class _E2EImageStorage:
        def __init__(self, bucket_name: str = "mlops-images") -> None:
            self.bucket_name = bucket_name
            self._objects: dict[str, tuple[bytes, str]] = {}

        def upload_bytes(self, object_name: str, data: bytes, *, content_type: str) -> None:
            self._objects[object_name] = (data, content_type)

        def exists(self, object_name: str) -> bool:
            return object_name in self._objects

        def download_bytes(self, object_name: str) -> bytes:
            return self._objects[object_name][0]

    class _E2EConfiguredAnalyzer:
        async def analyze_product_image_bytes(
            self,
            image_bytes: bytes,  # noqa: ARG002
            mime_type: str,  # noqa: ARG002
            *,
            filename: str | None = None,  # noqa: ARG002
            price_estimator: Any | None = None,  # noqa: ARG002
        ):
            from product_analyzer.schema import AnalyzeProductImageResponse, PriceEstimate

            return AnalyzeProductImageResponse(
                product_name="Apple AirPods Pro",
                brand="Apple",
                model="AirPods Pro",
                category="Earbud Headphones",
                condition_estimate="good",
                visible_text=["Apple", "AirPods Pro"],
                confidence=0.96,
                price_estimate=PriceEstimate(
                    low=110,
                    high=160,
                    currency="USD",
                    reasoning="Estimated from comparable products",
                    comparable_sources=[],
                ),
            )

    class _E2EConfiguredEbayClient:
        def __init__(self) -> None:
            self._sandbox = False

        def get_category_suggestions(self, query: str, *, marketplace_id: str | None = None):  # noqa: ARG002
            return [
                type(
                    "CategorySuggestion",
                    (),
                    {
                        "category_id": "9355",
                        "category_name": "Headphones",
                        "category_tree_id": "0",
                        "category_tree_version": None,
                        "path": ["Electronics", "Portable Audio"],
                    },
                )()
            ]

        def get_valid_conditions(self, category_id: str, *, marketplace_id: str | None = None):  # noqa: ARG002
            return ["NEW", "USED_EXCELLENT", "USED_GOOD"]

        def get_item_aspects_for_category(self, category_id: str, *, category_tree_id: str | None = None):  # noqa: ARG002
            return [
                {"localizedAspectName": "Brand", "aspectConstraint": {"aspectRequired": True}},
                {"localizedAspectName": "Model", "aspectConstraint": {"aspectRequired": True}},
                {
                    "localizedAspectName": "Color",
                    "aspectConstraint": {"aspectRequired": True},
                    "aspectValues": [{"localizedValue": "White"}, {"localizedValue": "Black"}],
                },
                {
                    "localizedAspectName": "Connectivity",
                    "aspectConstraint": {"aspectRequired": True},
                    "aspectValues": [{"localizedValue": "Bluetooth"}, {"localizedValue": "Wired"}],
                },
            ]

    class _E2EListingSeed(BaseModel):
        id: str
        marketplace_url: str
        image_url: str = ""
        created_at: datetime | None = None
        status: str = "draft"
        description: str = ""

    class _E2EPostSeed(BaseModel):
        name: str
        description: str = ""
        image_urls: list[str] = Field(default_factory=list)
        analysis: dict | None = None
        listings: list[_E2EListingSeed] = Field(default_factory=list)

    @app.post("/__e2e__/reset-posts")
    def e2e_reset_posts() -> dict:
        """In-memory only: new repository so Playwright tests start from an empty list."""
        if app_state.get("mongo_client") is not None:
            return {"ok": False, "reason": "not supported with MongoDB"}
        app_state["post_repository"] = InMemoryPostRepository()
        app_state["images_storage"] = None
        app_state["product_analyzer"] = ProductAnalyzer()
        app_state["ebay_client"] = None
        return {"ok": True}

    @app.post("/__e2e__/configure-airpods-upload")
    def e2e_configure_airpods_upload() -> dict[str, bool]:
        """Install test doubles so Playwright can exercise the real upload UI flow."""
        app_state["images_storage"] = _E2EImageStorage()
        app_state["product_analyzer"] = _E2EConfiguredAnalyzer()
        app_state["ebay_client"] = _E2EConfiguredEbayClient()
        return {"ok": True}

    @app.post("/__e2e__/seed-post")
    def e2e_seed_post(request: Request, seed: _E2EPostSeed) -> dict[str, Any]:
        """In-memory only: create a post with explicit analysis/listing state for browser E2E tests."""
        if app_state.get("mongo_client") is not None:
            raise HTTPException(status_code=400, detail="not supported with MongoDB")
        repo = get_post_repo()
        listings = [
            Listing(
                id=item.id,
                marketplace_url=item.marketplace_url,
                image_url=item.image_url,
                created_at=item.created_at or datetime.now(timezone.utc),
                status=item.status,
                description=item.description,
            )
            for item in seed.listings
        ]
        try:
            post = repo.create(
                seed.name,
                description=seed.description,
                image_urls=seed.image_urls,
                analysis=seed.analysis,
                listings=listings or None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return PostResponse.from_post(
            post,
            public_base=str(request.base_url),
            images_bucket=_images_bucket(),
        ).model_dump(mode="json")


@app.get("/health")
def health() -> dict:
    log.info("network.health")
    return {"status": "ok"}


@app.get("/auth/ebay/authorize", response_model=EbayAuthorizeResponse)
def ebay_authorize(user_id: str) -> EbayAuthorizeResponse:
    log.info("network.ebay_authorize user_id=%s", user_id)
    settings = app_state["cloud_settings"]
    if not settings.ebay_runame:
        raise HTTPException(status_code=503, detail="EBAY_RUNAME not configured")
    state = _make_ebay_state(user_id, settings)
    scopes = list(DEFAULT_USER_SCOPES)
    authorization_url = _get_ebay_client(settings).build_user_consent_url(
        runame=settings.ebay_runame,
        state=state,
        scopes=DEFAULT_USER_SCOPES,
    )
    return EbayAuthorizeResponse(
        authorization_url=authorization_url,
        state=state,
        scopes=scopes,
    )


@app.get("/auth/ebay/callback", response_model=EbayCallbackResponse)
def ebay_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    repo: EbayTokenRepository = Depends(get_ebay_token_repo),
) -> EbayCallbackResponse:
    log.info(
        "network.ebay_callback code_present=%s state_present=%s error_present=%s",
        bool(code),
        bool(state),
        bool(error),
    )
    return _store_ebay_callback(
        code=code,
        state=state,
        error=error,
        error_description=error_description,
        repo=repo,
    )


@app.get("/ebay/listings", response_model=EbayListingsResponse)
def ebay_listings(
    user: str,
    repo: EbayTokenRepository = Depends(get_ebay_token_repo),
) -> EbayListingsResponse:
    log.info("network.ebay_listings user=%s", user)
    token = repo.get_by_user_id(user)
    if token is None:
        raise HTTPException(status_code=404, detail="ebay token not found")

    settings = app_state["cloud_settings"]
    client = _get_ebay_client(settings)
    token = _get_valid_ebay_user_token(user, repo=repo, client=client)

    listings: list[EbayListingSummaryResponse] = []
    offset = 0
    limit = 200
    while True:
        skus, next_url = client.get_inventory_items(
            token.access_token,
            limit=limit,
            offset=offset,
        )
        for sku in skus:
            offers = client.get_offers(
                token.access_token,
                sku=sku,
            )
            listings.extend(
                EbayListingSummaryResponse(
                    sku=offer.sku,
                    offer_id=offer.offer_id,
                    listing_id=offer.listing_id,
                    marketplace_id=offer.marketplace_id,
                    format=offer.format,
                    available_quantity=offer.available_quantity,
                    category_id=offer.category_id,
                    merchant_location_key=offer.merchant_location_key,
                    listing_description=offer.listing_description,
                    status=offer.status,
                    price=offer.price,
                    currency=offer.currency,
                )
                for offer in offers
            )
        if not next_url or len(skus) < limit:
            break
        offset += len(skus)

    return EbayListingsResponse(user_id=user, listings=listings)


@app.get("/auth/ebay/accepted", response_class=HTMLResponse)
def ebay_authorization_accepted(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    repo: EbayTokenRepository = Depends(get_ebay_token_repo),
) -> HTMLResponse:
    log.info(
        "network.ebay_authorization_accepted code_present=%s state_present=%s",
        bool(code),
        bool(state),
    )
    _store_ebay_callback(
        code=code,
        state=state,
        error=error,
        error_description=error_description,
        repo=repo,
    )
    return HTMLResponse(
        "<html><body><h1>eBay authorization accepted</h1><p>You can close this window.</p></body></html>"
    )


@app.get("/auth/ebay/rejected", response_class=HTMLResponse)
def ebay_authorization_rejected(
    error: str | None = None,
    error_description: str | None = None,
    state: str | None = None,
) -> HTMLResponse:
    log.info("network.ebay_authorization_rejected error_present=%s", bool(error))
    logger.warning(
        "ebay authorization rejected callback",
        extra={"error": error, "error_description": error_description, "state_present": bool(state)},
    )
    message = html.escape(error_description or error or "The authorization request was rejected.")
    return HTMLResponse(f"<html><body><h1>eBay authorization rejected</h1><p>{message}</p></body></html>")


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
    log.info("network.http_get_post_image object_path=%s", object_path)
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
    ebay_draft: dict | None = None

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
            ebay_draft=post.ebay_draft,
        )


_POST_IMAGE_TYPES = frozenset(
    ("image/jpeg", "image/png", "image/webp", "image/gif"),
)
_MAX_IMAGE_BYTES = 12 * 1024 * 1024
_MAX_IMAGE_FILES = 24


_ANALYZER_SUPPORTED_TYPES = frozenset(("image/jpeg", "image/png", "image/webp"))


async def _upload_image_files_to_gcs(
    post_id: str, uploads: list[UploadFile], storage: GoogleCloudStorage
) -> tuple[list[str], tuple[bytes, str] | None]:
    """Upload images to private GCS.

    Returns ``(object_keys, first_supported)`` where ``first_supported`` is the
    bytes + MIME of the first JPEG/PNG upload (or ``None``) so the caller can
    pass it to the product analyzer without re-reading the form.
    """
    log.info(
        "controller._upload_image_files_to_gcs post_id=%s upload_count=%d",
        post_id,
        len(uploads),
    )
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
    log.info("network.http_get_posts name=%s include_deleted=%s", name, include_deleted)
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
    log.info("network.http_get_post post_id=%s include_deleted=%s", post_id, include_deleted)
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
    log.info("network.http_create_post content_type=%s", request.headers.get("content-type"))
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
    body_user_id = form.get("user_id")
    user_id = body_user_id.strip() if isinstance(body_user_id, str) and body_user_id.strip() else None
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
            parsed = await get_product_analyzer().analyze_product_image_bytes(image_bytes, image_mime)
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
    if analysis_result is not None and user_id is not None:
        try:
            draft = _build_ebay_draft(
                post=post,
                analysis=analysis_result,
                user_id=user_id,
                settings=app_state["cloud_settings"],
            )
            updated = repo.set_ebay_draft(post.id, draft)
            if updated is not None:
                post = updated
        except Exception as exc:  # noqa: BLE001
            log.warning("ebay draft creation skipped for post %s: %s", post_id, exc)
    return PostResponse.from_post(
        post,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


class UpdateEbayDraftRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    condition: str | None = None
    price: float | None = None
    currency: str | None = None
    item_specifics: dict[str, list[str]] | None = None


@app.put("/posts/{post_id}/ebay-draft", response_model=PostResponse)
def http_update_ebay_draft(
    request: Request,
    post_id: str,
    req: UpdateEbayDraftRequest,
    repo: PostRepository = Depends(get_post_repo),
) -> PostResponse:
    log.info("network.http_update_ebay_draft post_id=%s", post_id)
    post = repo.get_by_id(post_id, include_deleted=False)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if post.ebay_draft is None:
        raise HTTPException(status_code=404, detail="no eBay draft for this post")
    draft = dict(post.ebay_draft)
    if req.title is not None:
        draft["title"] = req.title
    if req.description is not None:
        draft["description"] = req.description
    if req.condition is not None:
        draft["condition"] = req.condition
    if req.price is not None:
        draft["price"] = req.price
    if req.currency is not None:
        draft["currency"] = req.currency
    if req.item_specifics is not None:
        draft["item_specifics"] = req.item_specifics
    updated = repo.set_ebay_draft(post_id, draft)
    if updated is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(
        updated,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


@app.post("/posts/{post_id}/ebay/publish", response_model=PostResponse)
def http_publish_ebay_listing(
    request: Request,
    post_id: str,
    repo: PostRepository = Depends(get_post_repo),
    token_repo: EbayTokenRepository = Depends(get_ebay_token_repo),
) -> PostResponse:
    log.info("network.http_publish_ebay_listing post_id=%s", post_id)
    post = repo.get_by_id(post_id, include_deleted=False)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if not post.ebay_draft:
        raise HTTPException(status_code=422, detail="no eBay draft to publish")
    settings = app_state["cloud_settings"]
    try:
        listing = _publish_ebay_from_draft(
            post=post,
            draft=post.ebay_draft,
            public_base=str(request.base_url),
            settings=settings,
            repo=token_repo,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    updated = repo.replace_listings(post.id, [listing])
    if updated is not None:
        updated = repo.set_ebay_draft(post.id, None)
    if updated is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(
        updated,
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
    log.info(
        "network.http_update_post post_id=%s name_present=%s description_present=%s",
        post_id,
        req.name is not None,
        req.description is not None,
    )
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
    log.info("network.http_delete_post post_id=%s", post_id)
    post = repo.soft_delete(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostResponse.from_post(
        post,
        public_base=str(request.base_url),
        images_bucket=_images_bucket(),
    )


def _configure_static_ui() -> None:
    """Mount the built React UI when ``static/`` exists; fall back to a JSON root otherwise.

    StaticFiles mounted at "/" intercepts every path before FastAPI routes can
    match, so we instead serve index.html explicitly for "/" and "/welcome" and
    mount the static assets directory at "/assets" (and individual known files).
    """
    static_root = Path(os.environ.get("STATIC_DIR", str(Path(__file__).resolve().parent / "static")))
    index_html = static_root / "index.html"

    def _serve_index() -> FileResponse:
        if not index_html.is_file():
            raise HTTPException(status_code=404, detail="UI not built — run `npm run build` first")
        return FileResponse(index_html)

    @app.get("/welcome", include_in_schema=False)
    def welcome_page() -> FileResponse:
        return _serve_index()

    if static_root.is_dir():
        # Mount assets sub-directory so hashed JS/CSS bundles resolve.
        assets_dir = static_root / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve known top-level static files explicitly.
        for filename in ("favicon.svg", "icons.svg", "demo-photo.jpg", "desk-photo.jpg"):
            filepath = static_root / filename
            if filepath.is_file():
                _path = f"/{filename}"
                _fp = filepath  # capture for closure

                @app.get(_path, include_in_schema=False)
                def _static_file(fp: Path = _fp) -> FileResponse:
                    return FileResponse(fp)

        @app.get("/", include_in_schema=False)
        def root() -> FileResponse:
            return _serve_index()
    else:

        @app.get("/")
        def root_json() -> dict:
            return {"message": "Welcome to mlops fastapi!"}


_configure_static_ui()


def main() -> None:
    log.info("mlops app module loaded")


if __name__ == "__main__":
    main()
