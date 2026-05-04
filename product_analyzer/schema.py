from __future__ import annotations

from pydantic import BaseModel, Field


class PriceEstimate(BaseModel):
    low: int = 0
    high: int = 0
    currency: str = "USD"
    reasoning: str = ""
    comparable_sources: list[str] = Field(default_factory=list)


class AnalyzeProductImageResponse(BaseModel):
    product_name: str = ""
    brand: str = ""
    model: str = ""
    category: str = ""
    condition_estimate: str = ""
    visible_text: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    price_estimate: PriceEstimate = Field(default_factory=PriceEstimate)
