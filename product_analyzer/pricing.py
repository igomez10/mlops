from __future__ import annotations

from typing import Protocol

from .schema import AnalyzeProductImageResponse, PriceEstimate


class PriceEstimator(Protocol):
    """Seam for future eBay / Amazon / Google Shopping comparables lookups."""

    def estimate(self, analysis: AnalyzeProductImageResponse) -> PriceEstimate: ...


class GeminiPriceEstimator:
    """Default: trust the price_estimate block Gemini already returned."""

    def estimate(self, analysis: AnalyzeProductImageResponse) -> PriceEstimate:
        return analysis.price_estimate


# Skeletons for teammates to plug into later. Not wired anywhere yet.
#
# class EbayPriceEstimator:
#     def estimate(self, analysis): ...  # query eBay Browse API "sold" comps
#
# class AmazonPriceEstimator:
#     def estimate(self, analysis): ...  # query Amazon PA-API
#
# class GoogleShoppingPriceEstimator:
#     def estimate(self, analysis): ...  # query Google Shopping
