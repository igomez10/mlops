from __future__ import annotations

import time

from fastapi import HTTPException, UploadFile

from product_analyzer.encoding import image_to_base64
from product_analyzer.evaluation import evaluate
from product_analyzer.gemini_vision import _default_model, call_gemini
from product_analyzer.parser import parse_gemini_json
from product_analyzer.pricing import GeminiPriceEstimator, PriceEstimator
from product_analyzer.prompt import PROMPT
from product_analyzer.schema import AnalyzeProductImageResponse
from product_analyzer.tracking import prompt_hash, track_run
from product_analyzer.validation import validate_image


async def analyze_product_image(
    upload: UploadFile,
    *,
    price_estimator: PriceEstimator | None = None,
) -> AnalyzeProductImageResponse:
    """End-to-end: UploadFile -> validated bytes -> Gemini -> parsed response.

    Each request opens one MLflow run (best-effort) and logs params, latency,
    token usage, parse outcome, evaluation metrics, and artifacts.
    """
    data, mime = await validate_image(upload)
    _ = image_to_base64(data)

    with track_run() as rec:
        rec.set_param("model", _default_model())
        rec.set_param("mime", mime)
        rec.set_param("image_size_bytes", len(data))
        rec.set_param("prompt_hash", prompt_hash(PROMPT))
        rec.set_param("media_resolution", "media_resolution_high")
        rec.set_text("prompt.txt", PROMPT)
        ext = "jpg" if mime == "image/jpeg" else "png"
        rec.set_image(f"input_image.{ext}", data)

        started = time.perf_counter()
        try:
            raw, usage = call_gemini(data, mime)
        except RuntimeError as exc:
            rec.set_metric("latency_seconds", time.perf_counter() - started)
            rec.set_metric("parse_ok", 0.0)
            rec.update_metrics(evaluate("", None))
            message = str(exc)
            if "GEMINI_API_KEY" in message:
                raise HTTPException(status_code=503, detail=message) from exc
            raise HTTPException(status_code=502, detail=message) from exc

        rec.set_metric("latency_seconds", time.perf_counter() - started)
        rec.update_metrics(usage)
        rec.set_text("raw_gemini_response.txt", raw)

        try:
            analysis = parse_gemini_json(raw)
        except ValueError as exc:
            rec.set_metric("parse_ok", 0.0)
            rec.update_metrics(evaluate(raw, None))
            raise HTTPException(
                status_code=502,
                detail=f"Could not parse Gemini response: {exc}",
            ) from exc

        rec.set_metric("parse_ok", 1.0)
        rec.set_metric("parsed_confidence_score", analysis.confidence)
        parsed_dict = analysis.model_dump()
        rec.update_metrics(evaluate(raw, parsed_dict))
        rec.set_text("parsed_output.json", analysis.model_dump_json(indent=2))

        estimator: PriceEstimator = price_estimator or GeminiPriceEstimator()
        analysis.price_estimate = estimator.estimate(analysis)
        return analysis
