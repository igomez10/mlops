from __future__ import annotations

from product_analyzer.evaluation import evaluate


def _full_payload() -> dict:
    return {
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


def test_happy_path_all_checks_pass():
    metrics = evaluate("ignored when parsed is given", _full_payload())
    assert metrics["eval_valid_json"] == 1.0
    assert metrics["eval_has_product_name"] == 1.0
    assert metrics["eval_has_brand"] == 1.0
    assert metrics["eval_has_category"] == 1.0
    assert metrics["eval_has_price"] == 1.0
    assert metrics["eval_price_valid_range"] == 1.0
    assert metrics["eval_score"] == 1.0


def test_empty_parsed_dict_with_valid_raw_json():
    metrics = evaluate("{}", {})
    assert metrics["eval_valid_json"] == 1.0
    assert metrics["eval_has_product_name"] == 0.0
    assert metrics["eval_has_brand"] == 0.0
    assert metrics["eval_has_category"] == 0.0
    assert metrics["eval_has_price"] == 0.0
    assert metrics["eval_price_valid_range"] == 0.0
    assert metrics["eval_score"] == 1.0 / 6.0


def test_invalid_raw_text_and_no_parsed():
    metrics = evaluate("not json at all {", None)
    assert metrics["eval_valid_json"] == 0.0
    assert metrics["eval_score"] == 0.0


def test_zero_price_marks_has_price_but_not_valid_range():
    payload = _full_payload()
    payload["price_estimate"]["low"] = 0
    payload["price_estimate"]["high"] = 0
    metrics = evaluate("", payload)
    assert metrics["eval_has_price"] == 1.0
    assert metrics["eval_price_valid_range"] == 0.0


def test_low_greater_than_high_invalid_range():
    payload = _full_payload()
    payload["price_estimate"]["low"] = 200
    payload["price_estimate"]["high"] = 100
    metrics = evaluate("", payload)
    assert metrics["eval_price_valid_range"] == 0.0


def test_string_prices_invalid_range():
    payload = _full_payload()
    payload["price_estimate"]["low"] = "120"
    payload["price_estimate"]["high"] = "180"
    metrics = evaluate("", payload)
    assert metrics["eval_price_valid_range"] == 0.0


def test_bool_prices_rejected():
    payload = _full_payload()
    payload["price_estimate"]["low"] = True
    payload["price_estimate"]["high"] = True
    metrics = evaluate("", payload)
    assert metrics["eval_price_valid_range"] == 0.0


def test_whitespace_only_strings_treated_as_empty():
    payload = _full_payload()
    payload["product_name"] = "   "
    metrics = evaluate("", payload)
    assert metrics["eval_has_product_name"] == 0.0


def test_score_is_mean_of_six_checks():
    payload = _full_payload()
    payload["brand"] = ""
    payload["category"] = ""
    metrics = evaluate("", payload)
    # 4 of 6 checks pass -> score (sum of 6 checks + score) keys
    expected_score = (1.0 + 1.0 + 0.0 + 0.0 + 1.0 + 1.0) / 6.0
    assert metrics["eval_score"] == expected_score
