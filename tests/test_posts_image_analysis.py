"""Integration tests: POST /posts calls the shared product analyzer for the
first JPEG/PNG upload, persists the analysis on the post, and never lets a
Gemini/MLflow failure block post creation.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pkg import EbayUserToken, InMemoryEbayTokenRepository
from product_analyzer import ProductAnalyzer
from product_analyzer.parser import parse_gemini_json
from product_analyzer.schema import AnalyzeProductImageResponse, PriceEstimate
from server import app, app_state


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _fake_analysis() -> AnalyzeProductImageResponse:
    return AnalyzeProductImageResponse(
        product_name="Sony WH-1000XM4",
        brand="Sony",
        model="WH-1000XM4",
        category="Headphones",
        condition_estimate="good",
        visible_text=["SONY"],
        confidence=0.9,
        price_estimate=PriceEstimate(
            low=120,
            high=180,
            currency="USD",
            reasoning="r",
            comparable_sources=[],
        ),
    )


def _make_storage_mock() -> MagicMock:
    store = MagicMock()
    store.bucket_name = "mlops-images"
    store.upload_bytes = MagicMock()
    return store


def _make_analyzer_mock(method) -> SimpleNamespace:
    return SimpleNamespace(analyze_product_image_bytes=method)


def _valid_gemini_json() -> str:
    return json.dumps(_fake_analysis().model_dump(mode="json"))


def _fixture_image(name: str) -> Path:
    return Path("fixtures") / name


def _seed_ebay_repo(user_id: str) -> InMemoryEbayTokenRepository:
    repo = InMemoryEbayTokenRepository()
    repo.upsert(
        EbayUserToken(
            user_id=user_id,
            access_token="user-access-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    return repo


def _assert_live_gemini_auth_configured() -> None:
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    )
    if not project:
        pytest.fail("GOOGLE_CLOUD_PROJECT must be set to run live Gemini tests with ADC auth")


def test_post_create_attaches_analysis_from_shared_function(client: TestClient) -> None:
    """The /posts handler should call analyze_product_image_bytes for the first
    JPEG/PNG and persist the result on the post."""
    called = {}

    async def _spy(image_bytes, mime_type, *, filename=None, price_estimator=None):
        called["bytes_len"] = len(image_bytes)
        called["mime"] = mime_type
        return _fake_analysis()

    app_state["product_analyzer"] = _make_analyzer_mock(_spy)
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "headphones"},
            files=[("files", ("a.png", b"\x89PNG\r\n\x1a\n abc", "image/png"))],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is not None
        assert body["analysis"]["product_name"] == "Sony WH-1000XM4"
        assert body["analysis"]["price_estimate"]["low"] == 120
        get_r = client.get(f"/posts/{body['id']}")
        assert get_r.status_code == 200, get_r.text
        fetched = get_r.json()
        assert fetched["analysis"] == body["analysis"]
        # And the analyzer was actually called with the uploaded image's bytes/mime.
        assert called["mime"] == "image/png"
        assert called["bytes_len"] == len(b"\x89PNG\r\n\x1a\n abc")
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_post_create_succeeds_when_analyzer_raises(client: TestClient) -> None:
    """Gemini/MLflow failure must not block post creation; analysis stays None."""

    async def _boom(image_bytes, mime_type, *, filename=None, price_estimator=None):
        raise RuntimeError("gemini exploded")

    app_state["product_analyzer"] = _make_analyzer_mock(_boom)
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "still works"},
            files=[("files", ("a.png", b"\x89PNG\r\n", "image/png"))],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is None
        assert body["description"] == "still works"
        assert len(body["image_urls"]) == 1
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_post_create_skips_analyzer_for_unsupported_mime(client: TestClient) -> None:
    """gif uploads are stored but not analyzed; no analyzer call should happen."""
    spy = MagicMock()

    async def _spy(*args, **kwargs):
        spy(*args, **kwargs)
        return _fake_analysis()

    app_state["product_analyzer"] = _make_analyzer_mock(_spy)
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "gif only"},
            files=[("files", ("a.gif", b"GIF89a\x00\x00", "image/gif"))],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is None
        spy.assert_not_called()
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_post_create_uses_first_supported_image_when_mixed(client: TestClient) -> None:
    """When uploads include gif (unsupported) and webp/jpeg/png, only the
    first supported image should be analyzed (one call total)."""
    captured = []

    async def _spy(image_bytes, mime_type, *, filename=None, price_estimator=None):
        captured.append((len(image_bytes), mime_type))
        return _fake_analysis()

    app_state["product_analyzer"] = _make_analyzer_mock(_spy)
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "mixed"},
            files=[
                ("files", ("a.gif", b"GIF89a\x00\x00", "image/gif")),
                ("files", ("b.webp", b"RIFFwebp", "image/webp")),
                ("files", ("c.jpg", b"\xff\xd8\xff jpeg-bytes", "image/jpeg")),
            ],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is not None
        get_r = client.get(f"/posts/{body['id']}")
        assert get_r.status_code == 200, get_r.text
        assert get_r.json()["analysis"] == body["analysis"]
        assert len(captured) == 1
        assert captured[0][1] == "image/webp"
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_json_post_create_does_not_call_analyzer(client: TestClient) -> None:
    """JSON posts (no images) must not trigger the analyzer."""
    spy = MagicMock()
    app_state["product_analyzer"] = _make_analyzer_mock(spy)
    try:
        r = client.post("/posts", json={"name": "no-image-post"})
        assert r.status_code == 201
        assert r.json()["analysis"] is None
        spy.assert_not_called()
    finally:
        app_state.pop("product_analyzer", None)


def test_post_create_persists_analysis_end_to_end_with_real_analyzer_and_mocked_gemini(
    client: TestClient,
) -> None:
    """Exercise the actual /posts -> ProductAnalyzer -> parser path with mocked Gemini output."""

    def _fake_gemini(image_bytes: bytes, mime_type: str) -> tuple[str, dict[str, float]]:
        assert mime_type == "image/jpeg"
        assert image_bytes.startswith(b"\xff\xd8\xff")
        return _valid_gemini_json(), {"prompt_tokens": 11.0, "response_tokens": 7.0}

    app_state["product_analyzer"] = ProductAnalyzer(gemini_caller=_fake_gemini)
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "real analyzer path"},
            files=[("files", ("a.jpg", b"\xff\xd8\xff jpeg-bytes", "image/jpeg"))],
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["analysis"] is not None
        assert created["analysis"]["brand"] == "Sony"
        assert created["analysis"]["price_estimate"]["high"] == 180

        by_id = client.get(f"/posts/{created['id']}")
        assert by_id.status_code == 200, by_id.text
        fetched = by_id.json()
        assert fetched["analysis"] == created["analysis"]

        listed = client.get("/posts")
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        [row] = [row for row in rows if row["id"] == created["id"]]
        assert row["analysis"] == created["analysis"]
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_post_create_uploads_airpods_and_publishes_ebay_listing_end_to_end(
    client: TestClient,
) -> None:
    image_path = _fixture_image("airpods.jpg")
    assert image_path.exists(), f"missing fixture image: {image_path}"

    class _FakeEbayClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []
            self._sandbox = False

        def get_category_suggestions(self, query: str, *, marketplace_id: str | None = None):
            self.calls.append(("get_category_suggestions", query, marketplace_id))
            return [
                SimpleNamespace(
                    category_id="9355",
                    category_name="Cell Phones & Smartphones",
                    category_tree_id="0",
                    category_tree_version=None,
                    path=["Electronics"],
                )
            ]

        def get_valid_conditions(self, category_id: str, *, marketplace_id: str | None = None):
            self.calls.append(("get_valid_conditions", category_id))
            return ["NEW", "USED_EXCELLENT", "USED_GOOD"]

        def get_item_aspects_for_category(self, category_id: str, *, category_tree_id: str | None = None):
            self.calls.append(("get_item_aspects_for_category", category_id))
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

        def get_fulfillment_policies(self, user_token: str, *, marketplace_id: str | None = None):
            self.calls.append(("get_fulfillment_policies", user_token, marketplace_id))
            return [SimpleNamespace(policy_id="fulfill-1")]

        def get_payment_policies(self, user_token: str, *, marketplace_id: str | None = None):
            self.calls.append(("get_payment_policies", user_token, marketplace_id))
            return [SimpleNamespace(policy_id="payment-1")]

        def get_return_policies(self, user_token: str, *, marketplace_id: str | None = None):
            self.calls.append(("get_return_policies", user_token, marketplace_id))
            return [SimpleNamespace(policy_id="return-1")]

        def create_inventory_location(self, merchant_location_key: str, user_token: str, payload: dict):
            self.calls.append(("create_inventory_location", merchant_location_key, user_token, payload))

        def create_or_replace_inventory_item(self, sku: str, user_token: str, payload: dict):
            self.calls.append(("create_or_replace_inventory_item", sku, user_token, payload))

        def create_offer(self, user_token: str, payload: dict) -> str:
            self.calls.append(("create_offer", user_token, payload))
            return "offer-123"

        def publish_offer(self, offer_id: str, user_token: str) -> dict:
            self.calls.append(("publish_offer", offer_id, user_token))
            return {"listingId": "listing-123", "listingWebUrl": "https://www.ebay.com/itm/listing-123"}

        def get_offer(self, offer_id: str, user_token: str) -> dict:
            self.calls.append(("get_offer", offer_id, user_token))
            return {"offerId": offer_id, "listingId": "listing-123", "status": "PUBLISHED"}

        def update_offer(self, offer_id: str, user_token: str, payload: dict) -> dict:
            self.calls.append(("update_offer", offer_id, user_token, payload))
            return {}

    fake_client = _FakeEbayClient()

    def _fake_gemini(image_bytes: bytes, mime_type: str) -> tuple[str, dict[str, float]]:
        assert mime_type == "image/jpeg"
        assert image_bytes[:2] == b"\xff\xd8"
        body = _fake_analysis().model_copy(
            update={
                "product_name": "Apple AirPods Pro",
                "brand": "Apple",
                "model": "AirPods Pro",
                "category": "Earbud Headphones",
                "condition_estimate": "good",
                "price_estimate": PriceEstimate(
                    low=110,
                    high=160,
                    currency="USD",
                    reasoning="r",
                    comparable_sources=[],
                ),
            }
        )
        return json.dumps(body.model_dump(mode="json")), {"prompt_tokens": 10.0, "response_tokens": 8.0}

    app_state["product_analyzer"] = ProductAnalyzer(gemini_caller=_fake_gemini)
    app_state["images_storage"] = _make_storage_mock()
    app_state["ebay_token_repository"] = _seed_ebay_repo("user-123")
    try:
        with patch("server._get_ebay_client", lambda settings: fake_client), patch(
            "server.EbayDraftPrefillService._build_item_specifics",
            return_value={
                "Brand": ["Apple"],
                "Model": ["AirPods Pro"],
                "Color": ["White"],
                "Connectivity": ["Bluetooth"],
            },
        ):
            # Step 1: create post → should build draft, not publish
            response = client.post(
                "/posts",
                data={"description": "AirPods from image upload", "user_id": "user-123"},
                files=[("files", (image_path.name, image_path.read_bytes(), "image/jpeg"))],
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["analysis"] is not None
            assert body["analysis"]["product_name"] == "Apple AirPods Pro"

            # Draft was created, no published eBay listing yet
            assert not any("ebay.com" in (lst.get("marketplace_url") or "") for lst in body["listings"])
            assert body["ebay_draft"] is not None
            draft = body["ebay_draft"]
            assert draft["category_id"] == "9355"
            assert draft["item_specifics"]["Color"] == ["White"]
            assert draft["item_specifics"]["Connectivity"] == ["Bluetooth"]

            # Draft creation call sequence
            call_names = [call[0] for call in fake_client.calls]
            assert call_names == [
                "get_category_suggestions",
                "get_valid_conditions",
                "get_item_aspects_for_category",
            ]
            category_call = next(call for call in fake_client.calls if call[0] == "get_category_suggestions")
            assert category_call[1] == "Apple AirPods Pro"

            # Step 2: publish the draft
            fake_client.calls.clear()
            pub_r = client.post(f"/posts/{body['id']}/ebay/publish")
            assert pub_r.status_code == 200, pub_r.text
            pub_body = pub_r.json()

            assert len(pub_body["listings"]) == 1
            listing = pub_body["listings"][0]
            assert listing["id"] == "listing-123"
            assert listing["marketplace_url"] == "https://www.ebay.com/itm/listing-123"
            assert listing["status"] == "PUBLISHED"
            assert "Product: Apple AirPods Pro" in listing["description"]

            # Draft cleared after publish
            assert pub_body["ebay_draft"] is None

            # Publish call sequence
            pub_calls = [call[0] for call in fake_client.calls]
            assert pub_calls == [
                "get_valid_conditions",
                "get_fulfillment_policies",
                "get_payment_policies",
                "get_return_policies",
                "create_inventory_location",
                "create_or_replace_inventory_item",
                "create_offer",
                "publish_offer",
                "get_offer",
                "update_offer",
            ]
            update_call = next(c for c in fake_client.calls if c[0] == "update_offer")
            update_payload = update_call[3]
            post_id = pub_body["id"]
            assert f"/posts/{post_id}" in update_call[3]["listingDescription"]
            assert update_payload["listingDescription"].startswith(listing["description"])
            inventory_payload = [call for call in fake_client.calls if call[0] == "create_or_replace_inventory_item"][
                0
            ][3]
            assert inventory_payload["product"]["brand"] == "Apple"
            assert inventory_payload["product"]["mpn"] == "AirPods Pro"
            assert inventory_payload["product"]["imageUrls"][0].startswith("http://testserver/images/posts/")
            assert inventory_payload["product"].get("aspects", {}).get("Brand") == ["Apple"]
            assert inventory_payload["product"].get("aspects", {}).get("Color") == ["White"]
            assert inventory_payload["product"].get("aspects", {}).get("Connectivity") == ["Bluetooth"]
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


@pytest.mark.integration
def test_post_create_persists_analysis_with_mongo_and_real_analyzer_mocked_gemini(
    mongo_container,
) -> None:
    """Persist/read back analysis through the Mongo repository implementation."""

    def _fake_gemini(image_bytes: bytes, mime_type: str) -> tuple[str, dict[str, float]]:
        assert mime_type == "image/png"
        assert image_bytes.startswith(b"\x89PNG")
        return _valid_gemini_json(), {"prompt_tokens": 13.0, "response_tokens": 9.0}

    db = f"post_analysis_{uuid.uuid4().hex}"
    env = {
        "MONGODB_URI": mongo_container.get_connection_url(),
        "MONGO_DATABASE": db,
    }
    with patch.dict(os.environ, env, clear=False):
        with TestClient(app) as client:
            app_state["product_analyzer"] = ProductAnalyzer(gemini_caller=_fake_gemini)
            app_state["images_storage"] = _make_storage_mock()
            try:
                r = client.post(
                    "/posts",
                    data={"description": "mongo analysis"},
                    files=[("files", ("a.png", b"\x89PNG\r\n\x1a\n abc", "image/png"))],
                )
                assert r.status_code == 201, r.text
                created = r.json()
                assert created["analysis"] is not None
                assert created["analysis"]["product_name"] == "Sony WH-1000XM4"

                by_id = client.get(f"/posts/{created['id']}")
                assert by_id.status_code == 200, by_id.text
                assert by_id.json()["analysis"] == created["analysis"]
            finally:
                app_state.pop("product_analyzer", None)
                app_state["images_storage"] = None


@pytest.mark.live
def test_call_gemini_direct_live_api() -> None:
    """Direct live Gemini test: no mocks, no skip on API/runtime errors."""
    _assert_live_gemini_auth_configured()

    image_path = Path("product_analyzer/test_image.jpg")
    if not image_path.exists():
        pytest.fail(f"Live Gemini test image is missing: {image_path}")

    from product_analyzer.gemini_vision import call_gemini

    raw, usage = call_gemini(image_path.read_bytes(), "image/jpeg")
    parsed = parse_gemini_json(raw)

    assert parsed.product_name.strip()
    assert parsed.brand.strip() or parsed.category.strip()
    assert 0.0 <= parsed.confidence <= 1.0
    assert parsed.price_estimate.currency.strip()
    assert isinstance(usage, dict)


@pytest.mark.live
def test_post_create_populates_analysis_live_gemini(client: TestClient) -> None:
    """Live end-to-end test for POST /posts using the AirPods fixture and real Gemini auth."""
    _assert_live_gemini_auth_configured()

    image_path = _fixture_image("airpods.jpg")
    if not image_path.exists():
        pytest.fail(f"Live Gemini test image is missing: {image_path}")

    class _FakeEbayClient:
        def get_category_suggestions(self, query: str, *, marketplace_id: str | None = None):
            return [SimpleNamespace(category_id="9355")]

        def get_valid_conditions(self, category_id: str, *, marketplace_id: str | None = None):
            return ["NEW", "USED_EXCELLENT", "USED_GOOD"]

        def get_item_aspects_for_category(self, category_id: str, *, category_tree_id: str | None = None):
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

    app_state["product_analyzer"] = ProductAnalyzer()
    app_state["images_storage"] = _make_storage_mock()
    app_state["ebay_token_repository"] = _seed_ebay_repo("live-user")
    try:
        with patch("server._get_ebay_client", lambda settings: _FakeEbayClient()):
            r = client.post(
                "/posts",
                data={"description": "White Apple AirPods Pro Bluetooth earbuds", "user_id": "live-user"},
                files=[("files", (image_path.name, image_path.read_bytes(), "image/jpeg"))],
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["analysis"] is not None
            assert body["analysis"]["product_name"].strip()
            assert body["analysis"]["price_estimate"]["currency"].strip()
            assert body["ebay_draft"] is not None
            assert body["ebay_draft"]["item_specifics"]["Color"] == ["White"]
            assert body["ebay_draft"]["item_specifics"]["Connectivity"] == ["Bluetooth"]

            get_r = client.get(f"/posts/{body['id']}")
            assert get_r.status_code == 200, get_r.text
            fetched = get_r.json()
            assert fetched["analysis"] == body["analysis"]
            assert fetched["ebay_draft"]["item_specifics"]["Color"] == ["White"]
            assert fetched["ebay_draft"]["item_specifics"]["Connectivity"] == ["Bluetooth"]
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None
