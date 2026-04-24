# niki
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

from product_analyzer.router import router

# Load GEMINI_API_KEY (and optional GEMINI_MODEL) from product_analyzer/.env
# so `uvicorn product_analyzer.app:app` Just Works after copying .env.example.
load_dotenv(dotenv_path="product_analyzer/.env")

app = FastAPI(title="Product Analyzer MVP")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
