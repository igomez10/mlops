from __future__ import annotations

import os
from typing import Any, Protocol

from google import genai
from google.genai import types

from pkg.logging_context import get_logger

from .prompt import PROMPT

log = get_logger(__name__)

# JSON schema mirrors schema.py so Gemini returns exactly this shape.
_RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "product_name": {"type": "string"},
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "category": {"type": "string"},
        "condition_estimate": {"type": "string"},
        "visible_text": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "price_estimate": {
            "type": "object",
            "properties": {
                "low": {"type": "integer"},
                "high": {"type": "integer"},
                "currency": {"type": "string"},
                "reasoning": {"type": "string"},
                "comparable_sources": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["low", "high", "currency", "reasoning", "comparable_sources"],
        },
    },
    "required": [
        "product_name",
        "brand",
        "model",
        "category",
        "condition_estimate",
        "visible_text",
        "confidence",
        "price_estimate",
    ],
}


class _GenAIClientLike(Protocol):
    """Subset of google-genai client used here (lets tests inject a fake)."""

    models: Any


def _cloud_project() -> str | None:
    return os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or os.environ.get("GCLOUD_PROJECT")


def _build_client() -> genai.Client:
    project = _cloud_project()
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT, GCP_PROJECT, or GCLOUD_PROJECT is required for Gemini ADC auth.")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
    return genai.Client(
        vertexai=True,
        project=project,
        location=location,
    )


def _default_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _build_image_part(image_bytes: bytes, mime_type: str) -> types.Part:
    """Inline image Part."""
    blob = types.Blob(mime_type=mime_type, data=image_bytes)
    return types.Part(inline_data=blob)


def _build_config() -> types.GenerateContentConfig:
    """JSON output constrained to our schema when the SDK supports it."""
    try:
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=_RESPONSE_JSON_SCHEMA,
        )
    except (TypeError, ValueError):
        return types.GenerateContentConfig(response_mime_type="application/json")


def _extract_usage(response: Any) -> dict[str, float]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return {}
    out: dict[str, float] = {}
    for src, dst in (
        ("prompt_token_count", "prompt_tokens"),
        ("candidates_token_count", "response_tokens"),
        ("total_token_count", "total_tokens"),
    ):
        v = getattr(meta, src, None)
        if v is not None:
            out[dst] = float(v)
    return out


def call_gemini(
    image_bytes: bytes,
    mime_type: str,
    *,
    client: _GenAIClientLike | None = None,
    model: str | None = None,
) -> tuple[str, dict[str, float]]:
    """Send one image + the extraction prompt to Gemini.

    Returns (raw_response_text, usage_metrics). usage_metrics is empty if the
    SDK didn't return usage_metadata.
    """
    gen_client = client or _build_client()
    model_name = model or _default_model()
    log.info("gemini_vision.call_gemini model=%s mime=%s size_bytes=%d", model_name, mime_type, len(image_bytes))

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=PROMPT),
                _build_image_part(image_bytes, mime_type),
            ],
        )
    ]

    try:
        response = gen_client.models.generate_content(
            model=model_name,
            contents=contents,  # type: ignore[arg-type]
            config=_build_config(),
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text, _extract_usage(response)
