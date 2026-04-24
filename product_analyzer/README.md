# Product Analyzer MVP

One endpoint, one image, one Gemini call → structured product + price JSON.

Standalone — does not touch the posts app in `mlops/server.py`. Teammate will
embed this later.

## File layout

```
product_analyzer/
├── __init__.py
├── app.py              # FastAPI app (run this)
├── router.py           # POST /analyze-product-image
├── service.py          # analyze_product_image() orchestrator
├── validation.py       # validate_image()
├── encoding.py         # image_to_base64()
├── gemini_vision.py    # call_gemini() — multimodal Gemini 3 call
├── parser.py           # parse_gemini_json()
├── pricing.py          # PriceEstimator seam (eBay/Amazon/Google later)
├── prompt.py           # extraction + price prompt
├── schema.py           # Pydantic response models
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

```bash
cd /Users/nikkinaderzad/Desktop/MLOps/mlops

# fresh virtualenv just for this MVP (recommended)
python -m venv .venv-mvp
source .venv-mvp/bin/activate

pip install -r product_analyzer/requirements.txt

cp product_analyzer/.env.example product_analyzer/.env
# edit product_analyzer/.env and set GEMINI_API_KEY
```

## Run

```bash
# From the mlops/ directory:
uvicorn product_analyzer.app:app --reload --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/health
```

## Test with one image

```bash
curl -X POST http://127.0.0.1:8001/analyze-product-image \
  -F "file=@/path/to/product.jpg"
```

Expected response:

```json
{
  "product_name": "Sony WH-1000XM4",
  "brand": "Sony",
  "model": "WH-1000XM4",
  "category": "Headphones",
  "condition_estimate": "good",
  "visible_text": ["SONY", "WH-1000XM4"],
  "confidence": 0.87,
  "price_estimate": {
    "low": 120,
    "high": 180,
    "currency": "USD",
    "reasoning": "Used XM4 headphones typically resell for $120–180 on eBay depending on cosmetic wear.",
    "comparable_sources": []
  }
}
```

## How it works (beginner tour)

### 1. Image upload
FastAPI parses the `multipart/form-data` and gives us a `UploadFile`
([`validation.py`](./validation.py)). We check the MIME type
(`image/jpeg` / `image/png`), enforce a 12 MB cap, and read the raw bytes.

### 2. Sending to Gemini
[`gemini_vision.py`](./gemini_vision.py) builds a `types.Part` with
`inline_data=types.Blob(mime_type=..., data=image_bytes)` and sets
`media_resolution={"level": "media_resolution_high"}` so Gemini 3 allocates
extra tokens per image and can read labels, logos, model numbers, and small
print. We also ask for JSON output (`response_mime_type="application/json"`)
constrained to the schema in `_RESPONSE_JSON_SCHEMA`.

The `google-genai` SDK takes raw bytes directly and base64-encodes them on
the wire for you. `image_to_base64()` in [`encoding.py`](./encoding.py) is
kept as a separate helper because the spec asked for it — useful for logging
or if you ever want to talk to the HTTP API directly without the SDK.

### 3. JSON response
[`parser.py`](./parser.py) strips any stray code fences, `json.loads` the
text, and validates it against `AnalyzeProductImageResponse` (Pydantic). If
the model hallucinates bad JSON or a wrong shape, we raise `HTTPException
502` with the parse error.

### 4. Where eBay / Amazon / Google Shopping plug in
[`pricing.py`](./pricing.py) defines a `PriceEstimator` Protocol. Today the
default is `GeminiPriceEstimator`, which just returns the `price_estimate`
block Gemini already produced.

When you're ready for real comparables:

```python
class EbayPriceEstimator:
    def estimate(self, analysis):
        # 1. Build a query from analysis.brand + analysis.model
        # 2. Hit eBay Browse API for sold listings
        # 3. Compute low = 25th percentile, high = 75th percentile
        # 4. Return PriceEstimate with comparable_sources populated
        ...
```

Then in [`service.py`](./service.py) pass your estimator in:

```python
return await analyze_product_image(file, price_estimator=EbayPriceEstimator())
```

No other code changes.

## Error handling

| Status | When                                                                  |
| ------ | --------------------------------------------------------------------- |
| 400    | Wrong MIME type, empty file, or file larger than 12 MB                |
| 422    | `file` form field missing (FastAPI default)                           |
| 502    | Gemini API call failed, or response wasn't valid JSON / right schema  |
| 503    | `GEMINI_API_KEY` not set in the environment                           |
