from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

from .router import router

# Load optional local config like GOOGLE_CLOUD_PROJECT / GEMINI_MODEL so
# `uvicorn product_analyzer.app:app` works in local development.
load_dotenv(dotenv_path="product_analyzer/.env")

app = FastAPI(title="Product Analyzer MVP")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
