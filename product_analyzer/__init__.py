"""Standalone MVP: one image in -> structured product details + price estimate out."""

from functools import lru_cache

from fastapi import UploadFile

from pkg.logging_context import get_logger

from .analyzer import ProductAnalyzer
from .gemini_vision import call_gemini
from .pricing import PriceEstimator
from .schema import AnalyzeProductImageResponse, PriceEstimate
from .validation import validate_image

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_default_product_analyzer() -> ProductAnalyzer:
    return ProductAnalyzer(gemini_caller=lambda image_bytes, mime_type: call_gemini(image_bytes, mime_type))


async def analyze_product_image(
    upload: UploadFile,
    *,
    price_estimator: PriceEstimator | None = None,
) -> AnalyzeProductImageResponse:
    log.info(
        "product_analyzer.analyze_product_image filename=%s content_type=%s",
        upload.filename,
        upload.content_type,
    )
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
    log.info(
        "product_analyzer.analyze_product_image_bytes mime=%s size_bytes=%d filename=%s",
        mime_type,
        len(image_bytes),
        filename,
    )
    return await get_default_product_analyzer().analyze_product_image_bytes(
        image_bytes,
        mime_type,
        filename=filename,
        price_estimator=price_estimator,
    )


__all__ = [
    "ProductAnalyzer",
    "AnalyzeProductImageResponse",
    "PriceEstimate",
    "analyze_product_image",
    "analyze_product_image_bytes",
    "get_default_product_analyzer",
]
