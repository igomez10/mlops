from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from product_analyzer.gemini_vision import _build_client, _default_model, call_gemini


def test_build_client_uses_vertex_adc_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-1")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    with patch("product_analyzer.gemini_vision.genai.Client") as client_cls:
        _build_client()
        client_cls.assert_called_once_with(
            vertexai=True,
            project="proj-1",
            location="us-central1",
        )


def test_build_client_requires_project(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        _build_client()


def test_default_model_uses_stable_vertex_friendly_default(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert _default_model() == "gemini-2.5-flash"


def test_call_gemini_sends_user_role() -> None:
    captured: dict[str, object] = {}
    response_json = json.dumps(
        {
            "product_name": "x",
            "brand": "x",
            "model": "x",
            "category": "x",
            "condition_estimate": "x",
            "visible_text": [],
            "confidence": 0.5,
            "price_estimate": {
                "low": 1,
                "high": 2,
                "currency": "USD",
                "reasoning": "r",
                "comparable_sources": [],
            },
        }
    )

    class _FakeModels:
        def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(text=response_json)

    fake_client = SimpleNamespace(models=_FakeModels())
    call_gemini(b"\xff\xd8\xff", "image/jpeg", client=fake_client, model="gemini-2.5-flash")

    [content] = captured["contents"]
    assert content.role == "user"
