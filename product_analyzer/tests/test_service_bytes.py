"""Tests for the importable bytes-based analyzer entrypoint.

These verify that ``analyze_product_image_bytes`` can be called directly
(without an UploadFile) — that's the shape server.py POST /posts uses.
"""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import MagicMock

import pytest

from product_analyzer import analyze_product_image_bytes

VALID_JSON = json.dumps(
    {
        "product_name": "Sony WH-1000XM4",
        "brand": "Sony",
        "model": "WH-1000XM4",
        "category": "Headphones",
        "condition_estimate": "good",
        "visible_text": ["SONY"],
        "confidence": 0.9,
        "price_estimate": {
            "low": 120,
            "high": 180,
            "currency": "USD",
            "reasoning": "...",
            "comparable_sources": [],
        },
    }
)


@pytest.fixture(autouse=True)
def _mlflow_off(monkeypatch):
    """Disable MLflow so tests don't try to talk to a real server."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.delenv("MLFLOW_TRACKING_ENABLED", raising=False)
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = MagicMock()
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)


def test_bytes_entrypoint_returns_parsed_response(monkeypatch):
    monkeypatch.setattr(
        "product_analyzer.call_gemini",
        lambda data, mime: (VALID_JSON, {"prompt_tokens": 10, "response_tokens": 5}),
    )

    result = asyncio.run(analyze_product_image_bytes(b"\xff\xd8\xff fake jpeg", "image/jpeg"))

    assert result.product_name == "Sony WH-1000XM4"
    assert result.brand == "Sony"
    assert result.price_estimate.low == 120
    assert result.price_estimate.high == 180


def test_bytes_entrypoint_accepts_filename_kwarg(monkeypatch):
    monkeypatch.setattr(
        "product_analyzer.call_gemini",
        lambda data, mime: (VALID_JSON, {}),
    )
    # filename is accepted but doesn't change behavior — just shouldn't raise.
    result = asyncio.run(analyze_product_image_bytes(b"\xff\xd8\xff", "image/jpeg", filename="phone.jpg"))
    assert result.product_name == "Sony WH-1000XM4"


def test_bytes_entrypoint_propagates_gemini_failure_as_502(monkeypatch):
    from fastapi import HTTPException

    def _boom(data, mime):
        raise RuntimeError("Gemini API call failed: boom")

    monkeypatch.setattr("product_analyzer.call_gemini", _boom)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(analyze_product_image_bytes(b"\xff\xd8\xff", "image/jpeg"))
    assert exc.value.status_code == 502


def test_bytes_entrypoint_missing_project_is_503(monkeypatch):
    from fastapi import HTTPException

    def _no_key(data, mime):
        raise RuntimeError("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) is required for Gemini ADC auth.")

    monkeypatch.setattr("product_analyzer.call_gemini", _no_key)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(analyze_product_image_bytes(b"\xff\xd8\xff", "image/jpeg"))
    assert exc.value.status_code == 503


def test_existing_upload_endpoint_still_uses_shared_function(monkeypatch):
    """analyze_product_image(UploadFile) must delegate to the bytes entrypoint
    so both paths share the same Gemini + MLflow logic.
    """
    called = {}

    async def _spy(image_bytes, mime_type, *, filename=None, price_estimator=None):
        called["bytes_len"] = len(image_bytes)
        called["mime"] = mime_type
        called["filename"] = filename
        # Re-use the shared function's normal return to keep the contract.
        from product_analyzer.schema import (
            AnalyzeProductImageResponse,
            PriceEstimate,
        )

        return AnalyzeProductImageResponse(
            product_name="x",
            brand="x",
            model="x",
            category="x",
            condition_estimate="x",
            visible_text=[],
            confidence=0.5,
            price_estimate=PriceEstimate(low=1, high=2, currency="USD", reasoning="r", comparable_sources=[]),
        )

    monkeypatch.setattr("product_analyzer.analyze_product_image_bytes", _spy)

    from io import BytesIO

    from fastapi import UploadFile as StarletteUploadFile
    from starlette.datastructures import Headers

    upload = StarletteUploadFile(
        filename="a.jpg",
        file=BytesIO(b"\xff\xd8\xff hello"),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    from product_analyzer import analyze_product_image

    result = asyncio.run(analyze_product_image(upload))
    assert result.product_name == "x"
    assert called["mime"] == "image/jpeg"
    assert called["filename"] == "a.jpg"
    assert called["bytes_len"] == len(b"\xff\xd8\xff hello")
