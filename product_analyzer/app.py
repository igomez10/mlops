from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.requests import Request

from pkg.logging_context import (
    REQUEST_ID_HEADER,
    configure_logging,
    get_logger,
    new_request_id,
    reset_request_id,
    set_request_id,
)

from .router import router

# Load optional local config like GOOGLE_CLOUD_PROJECT / GEMINI_MODEL so
# `uvicorn product_analyzer.app:app` works in local development.
load_dotenv(dotenv_path="product_analyzer/.env")

configure_logging()
log = get_logger(__name__)

app = FastAPI(title="Product Analyzer MVP")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Bind a request id so analyzer + Gemini logs can be correlated."""
    incoming = request.headers.get(REQUEST_ID_HEADER)
    request_id = incoming.strip() if incoming and incoming.strip() else new_request_id()
    token = set_request_id(request_id)
    log.info(
        "http.request.start method=%s path=%s request_id=%s",
        request.method,
        request.url.path,
        request_id,
    )
    try:
        response = await call_next(request)
    except Exception:
        log.exception("http.request.error method=%s path=%s", request.method, request.url.path)
        reset_request_id(token)
        raise
    response.headers[REQUEST_ID_HEADER] = request_id
    log.info(
        "http.request.end method=%s path=%s status=%d",
        request.method,
        request.url.path,
        response.status_code,
    )
    reset_request_id(token)
    return response


app.include_router(router)


@app.get("/health")
def health() -> dict:
    log.info("network.health (product_analyzer)")
    return {"status": "ok"}
