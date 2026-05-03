"""Integration tests: POST /posts calls the shared product analyzer for the
first JPEG/PNG upload, persists the analysis on the post, and never lets a
Gemini/MLflow failure block post creation.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

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
