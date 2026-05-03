from __future__ import annotations

import json
import sys
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from product_analyzer.app import app

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


# Minimal fake JPEG header bytes — enough for the multipart test; PIL is mocked.
_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _mlflow_env(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://fake:5000")
    monkeypatch.setenv("MLFLOW_TRACKING_ENABLED", "1")
    fake_mlflow = MagicMock()
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    fake_pil = MagicMock()
    fake_pil.Image.open.return_value = MagicMock()
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    yield fake_mlflow


def _post_image(client: TestClient) -> Any:
    return client.post(
        "/analyze-product-image",
        files={"file": ("test.jpg", BytesIO(_FAKE_JPEG), "image/jpeg")},
    )


def _metric_calls(fake_mlflow: MagicMock) -> dict[str, float]:
    return {c.args[0]: c.args[1] for c in fake_mlflow.log_metric.call_args_list}


def _param_calls(fake_mlflow: MagicMock) -> dict[str, object]:
    return {c.args[0]: c.args[1] for c in fake_mlflow.log_param.call_args_list}


def _text_calls(fake_mlflow: MagicMock) -> dict[str, str]:
    return {c.args[1]: c.args[0] for c in fake_mlflow.log_text.call_args_list}


def test_happy_path_logs_full_run(monkeypatch, _mlflow_env):
    fake_mlflow = _mlflow_env
    monkeypatch.setattr(
        "product_analyzer.service.call_gemini",
        lambda data, mime: (VALID_JSON, {"prompt_tokens": 10, "response_tokens": 5}),
    )

    with TestClient(app) as client:
        response = _post_image(client)

    assert response.status_code == 200
    fake_mlflow.start_run.assert_called_once_with(run_name="analyze-product-image")

    params = _param_calls(fake_mlflow)
    assert params["mime"] == "image/jpeg"
    assert params["image_size_bytes"] == len(_FAKE_JPEG)
    assert "prompt_hash" in params and len(params["prompt_hash"]) == 12
    assert params["media_resolution"] == "media_resolution_high"

    metrics = _metric_calls(fake_mlflow)
    assert metrics["parse_ok"] == 1.0
    assert metrics["eval_score"] == 1.0
    assert metrics["eval_valid_json"] == 1.0
    assert metrics["eval_has_brand"] == 1.0
    assert metrics["eval_price_valid_range"] == 1.0
    assert metrics["prompt_tokens"] == 10.0
    assert metrics["response_tokens"] == 5.0
    assert "latency_seconds" in metrics

    texts = _text_calls(fake_mlflow)
    assert "prompt.txt" in texts
    assert "raw_gemini_response.txt" in texts
    assert "parsed_output.json" in texts
    fake_mlflow.log_image.assert_called_once()
    assert fake_mlflow.log_image.call_args.args[1] == "input_image.jpg"


def test_gemini_failure_still_logs_best_effort(monkeypatch, _mlflow_env):
    fake_mlflow = _mlflow_env

    def _boom(data, mime):
        raise RuntimeError("Gemini API call failed: boom")

    monkeypatch.setattr("product_analyzer.service.call_gemini", _boom)

    with TestClient(app) as client:
        response = _post_image(client)

    assert response.status_code == 502
    fake_mlflow.start_run.assert_called_once()
    metrics = _metric_calls(fake_mlflow)
    assert "latency_seconds" in metrics
    assert metrics["parse_ok"] == 0.0
    assert metrics["eval_score"] == 0.0
    assert metrics["eval_valid_json"] == 0.0


def test_parse_failure_logs_zero_eval(monkeypatch, _mlflow_env):
    fake_mlflow = _mlflow_env
    monkeypatch.setattr(
        "product_analyzer.service.call_gemini",
        lambda data, mime: ("not json at all {", {}),
    )

    with TestClient(app) as client:
        response = _post_image(client)

    assert response.status_code == 502
    metrics = _metric_calls(fake_mlflow)
    assert metrics["parse_ok"] == 0.0
    assert metrics["eval_valid_json"] == 0.0

    texts = _text_calls(fake_mlflow)
    assert texts["raw_gemini_response.txt"] == "not json at all {"
    assert "parsed_output.json" not in texts


def test_missing_api_key_returns_503(monkeypatch, _mlflow_env):
    def _no_key(data, mime):
        raise RuntimeError("GEMINI_API_KEY is not set.")

    monkeypatch.setattr("product_analyzer.service.call_gemini", _no_key)

    with TestClient(app) as client:
        response = _post_image(client)

    assert response.status_code == 503
