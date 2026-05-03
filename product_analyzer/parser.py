# niki
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .schema import AnalyzeProductImageResponse

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def parse_gemini_json(raw: str) -> AnalyzeProductImageResponse:
    """Parse Gemini's raw text into the response schema.

    Raises ValueError on invalid JSON or schema mismatch; the caller decides
    how to surface the failure over HTTP.
    """
    cleaned = _strip_code_fences(raw)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Gemini JSON must be an object at the top level.")

    try:
        return AnalyzeProductImageResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Gemini JSON did not match expected schema: {exc}") from exc
