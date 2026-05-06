from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from pkg.logging_context import get_logger

from . import analyze_product_image
from .schema import AnalyzeProductImageResponse

log = get_logger(__name__)
router = APIRouter()


@router.post("/analyze-product-image", response_model=AnalyzeProductImageResponse)
async def http_analyze_product_image(
    file: UploadFile = File(..., description="One JPEG or PNG product image"),
) -> AnalyzeProductImageResponse:
    log.info(
        "network.http_analyze_product_image filename=%s content_type=%s",
        file.filename,
        file.content_type,
    )
    return await analyze_product_image(file)
