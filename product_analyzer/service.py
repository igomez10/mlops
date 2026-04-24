# niki
from __future__ import annotations

from fastapi import HTTPException, UploadFile

from product_analyzer.encoding import image_to_base64
from product_analyzer.gemini_vision import call_gemini
from product_analyzer.parser import parse_gemini_json
from product_analyzer.pricing import GeminiPriceEstimator, PriceEstimator
from product_analyzer.schema import AnalyzeProductImageResponse
from product_analyzer.validation import validate_image


async def analyze_product_image(
    upload: UploadFile,
    *,
    price_estimator: PriceEstimator | None = None,
) -> AnalyzeProductImageResponse:
    """End-to-end: UploadFile -> validated bytes -> Gemini -> parsed response."""
    data, mime = await validate_image(upload)

    # Kept for completeness + future use (logging, debugging, alternate transports).
    # The google-genai SDK takes raw bytes directly and base64-encodes on the wire.
    _ = image_to_base64(data)

    try:
        raw = call_gemini(data, mime)
    except RuntimeError as exc:
        message = str(exc)
        if "GEMINI_API_KEY" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=502, detail=message) from exc

    try:
        analysis = parse_gemini_json(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not parse Gemini response: {exc}",
        ) from exc

    estimator: PriceEstimator = price_estimator or GeminiPriceEstimator()
    analysis.price_estimate = estimator.estimate(analysis)
    return analysis
