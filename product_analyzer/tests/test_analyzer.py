from __future__ import annotations

import asyncio
import json
import sys
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile

from product_analyzer.analyzer import ProductAnalyzer
from product_analyzer.pricing import PriceEstimator
from product_analyzer.schema import AnalyzeProductImageResponse, PriceEstimate


class _FixedPriceEstimator(PriceEstimator):
    def estimate(self, analysis: AnalyzeProductImageResponse) -> PriceEstimate:
        return PriceEstimate(
            low=10,
            high=20,
            currency="USD",
            reasoning=f"priced:{analysis.product_name}",
            comparable_sources=["unit-test"],
        )


def _valid_json() -> str:
    return json.dumps(
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
                "reasoning": "model output",
                "comparable_sources": [],
            },
        }
    )


def _make_fake_pil() -> MagicMock:
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = MagicMock()
    return fake_pil


def test_product_analyzer_uses_injected_price_estimator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "PIL", _make_fake_pil())

    analyzer = ProductAnalyzer(
        gemini_caller=lambda data, mime: (_valid_json(), {"prompt_tokens": 1.0}),
        price_estimator=_FixedPriceEstimator(),
    )

    result = asyncio.run(analyzer.analyze_product_image_bytes(b"\xff\xd8\xff", "image/jpeg"))

    assert result.product_name == "Sony WH-1000XM4"
    assert result.price_estimate.low == 10
    assert result.price_estimate.high == 20
    assert result.price_estimate.comparable_sources == ["unit-test"]


def test_product_analyzer_upload_entrypoint_delegates_to_bytes_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "PIL", _make_fake_pil())
    captured = {}

    def _fake_gemini(data: bytes, mime: str) -> tuple[str, dict[str, float]]:
        captured["mime"] = mime
        captured["size"] = len(data)
        return _valid_json(), {}

    analyzer = ProductAnalyzer(gemini_caller=_fake_gemini)
    upload = StarletteUploadFile(
        filename="a.jpg",
        file=BytesIO(b"\xff\xd8\xff hello"),
        headers=Headers({"content-type": "image/jpeg"}),
    )

    result = asyncio.run(analyzer.analyze_product_image(upload))

    assert result.product_name == "Sony WH-1000XM4"
    assert captured["mime"] == "image/jpeg"
    assert captured["size"] == len(b"\xff\xd8\xff hello")
