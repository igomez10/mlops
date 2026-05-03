"""Integration tests: POST /posts calls the shared product analyzer for the
first JPEG/PNG upload, persists the analysis on the post, and never lets a
Gemini/MLflow failure block post creation.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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


def _assert_live_gemini_auth_configured() -> None:
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
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
    """webp/gif uploads are stored but not analyzed; no analyzer call should happen."""
    spy = MagicMock()

    async def _spy(*args, **kwargs):
        spy(*args, **kwargs)
        return _fake_analysis()

    app_state["product_analyzer"] = _make_analyzer_mock(_spy)
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "webp only"},
            files=[("files", ("a.webp", b"RIFF\x00\x00\x00\x00WEBP", "image/webp"))],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is None
        spy.assert_not_called()
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_post_create_uses_first_jpeg_png_when_mixed(client: TestClient) -> None:
    """When uploads include both unsupported and supported types, only the
    first JPEG/PNG should be analyzed (one call total)."""
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
                ("files", ("a.webp", b"RIFFwebp", "image/webp")),
                ("files", ("b.jpg", b"\xff\xd8\xff jpeg-bytes", "image/jpeg")),
                ("files", ("c.png", b"\x89PNG more", "image/png")),
            ],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is not None
        get_r = client.get(f"/posts/{body['id']}")
        assert get_r.status_code == 200, get_r.text
        assert get_r.json()["analysis"] == body["analysis"]
        assert len(captured) == 1
        assert captured[0][1] == "image/jpeg"
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None


def test_json_post_create_does_not_call_analyzer(client: TestClient) -> None:
    """JSON posts (no images) must not trigger the analyzer."""
    spy = MagicMock()
    app_state["product_analyzer"] = _make_analyzer_mock(spy)

    r = client.post("/posts", json={"name": "no-image-post"})
    assert r.status_code == 201
    assert r.json()["analysis"] is None
    spy.assert_not_called()
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
    """Live end-to-end test for POST /posts using a real image and real Gemini auth."""
    _assert_live_gemini_auth_configured()

    image_path = Path("product_analyzer/test_image.jpg")
    if not image_path.exists():
        pytest.fail(f"Live Gemini test image is missing: {image_path}")

    app_state["product_analyzer"] = ProductAnalyzer()
    app_state["images_storage"] = _make_storage_mock()
    try:
        r = client.post(
            "/posts",
            data={"description": "live gemini post analysis"},
            files=[("files", (image_path.name, image_path.read_bytes(), "image/jpeg"))],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["analysis"] is not None
        assert body["analysis"]["product_name"].strip()
        assert body["analysis"]["price_estimate"]["currency"].strip()

        get_r = client.get(f"/posts/{body['id']}")
        assert get_r.status_code == 200, get_r.text
        fetched = get_r.json()
        assert fetched["analysis"] == body["analysis"]
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None
