# niki
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from .schema import AnalyzeProductImageResponse
from .service import analyze_product_image

router = APIRouter()


@router.post("/analyze-product-image", response_model=AnalyzeProductImageResponse)
async def http_analyze_product_image(
    file: UploadFile = File(..., description="One JPEG or PNG product image"),
) -> AnalyzeProductImageResponse:
    return await analyze_product_image(file)
