from __future__ import annotations

from functools import lru_cache

from fastapi import UploadFile

from .analyzer import ProductAnalyzer
from .gemini_vision import call_gemini
from .pricing import PriceEstimator
from .schema import AnalyzeProductImageResponse
from .validation import validate_image


@lru_cache(maxsize=1)
def get_default_product_analyzer() -> ProductAnalyzer:
    return ProductAnalyzer(gemini_caller=lambda image_bytes, mime_type: call_gemini(image_bytes, mime_type))


async def analyze_product_image(
    upload: UploadFile,
    *,
    price_estimator: PriceEstimator | None = None,
) -> AnalyzeProductImageResponse:
    """Backward-compatible wrapper around the package default analyzer."""
    data, mime = await validate_image(upload)
    return await analyze_product_image_bytes(
        data,
        mime,
        filename=upload.filename,
        price_estimator=price_estimator,
    )


async def analyze_product_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    *,
    filename: str | None = None,
    price_estimator: PriceEstimator | None = None,
) -> AnalyzeProductImageResponse:
    """Backward-compatible wrapper around the package default analyzer."""
    return await get_default_product_analyzer().analyze_product_image_bytes(
        image_bytes,
        mime_type,
        filename=filename,
        price_estimator=price_estimator,
    )
