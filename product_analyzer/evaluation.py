from __future__ import annotations

import json
from numbers import Real
from typing import Any


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _has_valid_price_range(price: Any) -> bool:
    if not isinstance(price, dict):
        return False
    low, high = price.get("low"), price.get("high")
    # bool is a subclass of int/Real — exclude it explicitly.
    if isinstance(low, bool) or isinstance(high, bool):
        return False
    if not (isinstance(low, Real) and isinstance(high, Real)):
        return False
    return float(low) > 0 and float(high) > 0 and float(low) <= float(high)


def evaluate(raw_text: str, parsed: dict | None) -> dict[str, float]:
    """Score a Gemini analyzer response. Returns metrics in [0.0, 1.0]."""
    if parsed is not None:
        valid_json = 1.0
    else:
        try:
            json.loads(raw_text)
            valid_json = 1.0
        except (TypeError, ValueError):
            valid_json = 0.0

    p = parsed or {}
    checks = {
        "eval_valid_json": valid_json,
        "eval_has_product_name": float(_is_nonempty_str(p.get("product_name"))),
        "eval_has_brand": float(_is_nonempty_str(p.get("brand"))),
        "eval_has_category": float(_is_nonempty_str(p.get("category"))),
        "eval_has_price": float(isinstance(p.get("price_estimate"), dict)),
        "eval_price_valid_range": float(_has_valid_price_range(p.get("price_estimate"))),
    }
    checks["eval_score"] = sum(checks.values()) / len(checks)
    return checks
