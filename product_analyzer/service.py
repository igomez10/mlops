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
from product_analyzer.tracking import prompt_hash, start_span, track_run
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
    """Shared analyzer entrypoint for callers that already hold raw image bytes.

    Same behavior as ``analyze_product_image`` minus the UploadFile validation
    step (callers are expected to have validated MIME/size already). Used by
    server.py POST /posts so the post-creation flow doesn't re-read the upload.
    """
    data = image_bytes
    mime = mime_type
    _ = image_to_base64(data)
    _ = filename  # accepted for callers; not currently logged.

    model_name = _default_model()
    p_hash = prompt_hash(PROMPT)
    media_resolution = "media_resolution_high"

    with track_run() as rec:
        rec.set_param("model", model_name)
        rec.set_param("mime", mime)
        rec.set_param("image_size_bytes", len(data))
        rec.set_param("prompt_hash", p_hash)
        rec.set_param("media_resolution", media_resolution)
        rec.set_text("prompt.txt", PROMPT)
        ext = "jpg" if mime == "image/jpeg" else "png"
        rec.set_image(f"input_image.{ext}", data)

        span_attributes = {
            "gen_ai.system": "google.gemini",
            "gen_ai.request.model": model_name,
            "gen_ai.request.media_resolution": media_resolution,
            "image.mime_type": mime,
            "image.size_bytes": len(data),
            "prompt.hash": p_hash,
        }
        span_inputs = {
            "prompt_preview": PROMPT[:500],
            "prompt_hash": p_hash,
            "image": {"mime_type": mime, "size_bytes": len(data)},
        }

        started = time.perf_counter()
        with start_span(
            "gemini.generate_content",
            span_type="LLM",
            inputs=span_inputs,
            attributes=span_attributes,
        ) as span:
            try:
                raw, usage = call_gemini(data, mime)
            except RuntimeError as exc:
                latency = time.perf_counter() - started
                rec.set_metric("latency_seconds", latency)
                rec.set_metric("parse_ok", 0.0)
                rec.update_metrics(evaluate("", None))
                span.set_attributes(
                    {
                        "latency_seconds": latency,
                        "error.stage": "gemini_call",
                        "error.message": str(exc),
                    }
                )
                message = str(exc)
                if "GEMINI_API_KEY" in message:
                    raise HTTPException(status_code=503, detail=message) from exc
                raise HTTPException(status_code=502, detail=message) from exc

            latency = time.perf_counter() - started
            rec.set_metric("latency_seconds", latency)
            rec.update_metrics(usage)
            rec.set_text("raw_gemini_response.txt", raw)

            try:
                analysis = parse_gemini_json(raw)
            except ValueError as exc:
                rec.set_metric("parse_ok", 0.0)
                rec.update_metrics(evaluate(raw, None))
                span.set_outputs(
                    {
                        "raw_preview": raw[:500],
                        "parse_ok": False,
                    }
                )
                span.set_attributes(
                    {
                        "latency_seconds": latency,
                        "parse_ok": False,
                        "error.stage": "parse",
                        "error.message": str(exc),
                        **{f"gen_ai.usage.{k}": v for k, v in usage.items()},
                    }
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not parse Gemini response: {exc}",
                ) from exc

            rec.set_metric("parse_ok", 1.0)
            rec.set_metric("parsed_confidence_score", analysis.confidence)
            parsed_dict = analysis.model_dump()
            rec.update_metrics(evaluate(raw, parsed_dict))
            rec.set_text("parsed_output.json", analysis.model_dump_json(indent=2))

            span.set_outputs(
                {
                    "parse_ok": True,
                    "product_name": parsed_dict.get("product_name"),
                    "brand": parsed_dict.get("brand"),
                    "category": parsed_dict.get("category"),
                    "confidence": parsed_dict.get("confidence"),
                }
            )
            span.set_attributes(
                {
                    "latency_seconds": latency,
                    "parse_ok": True,
                    **{f"gen_ai.usage.{k}": v for k, v in usage.items()},
                }
            )

        estimator: PriceEstimator = price_estimator or GeminiPriceEstimator()
        analysis.price_estimate = estimator.estimate(analysis)
        return analysis
