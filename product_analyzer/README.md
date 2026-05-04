# Product Analyzer

`product_analyzer` is a reusable package that turns one uploaded image into structured product metadata plus a price estimate. The main backend uses it directly during post creation.

## Files

```text
product_analyzer/
├── __init__.py
├── analyzer.py
├── app.py
├── router.py
├── schema.py
├── validation.py
├── parser.py
├── prompt.py
├── gemini_vision.py
├── tracking.py
├── evaluation.py
├── pricing.py
└── tests/
```

## Runtime Model

- `ProductAnalyzer` in `analyzer.py` owns the workflow.
- `product_analyzer.__init__` exposes cached convenience wrappers:
  - `analyze_product_image(upload)`
  - `analyze_product_image_bytes(image_bytes, mime_type)`
- `router.py` uses those wrappers for the standalone FastAPI app.

## Standalone Run

```bash
uvicorn product_analyzer.app:app --reload --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/health
```

Analyze one image:

```bash
curl -X POST http://127.0.0.1:8001/analyze-product-image \
  -F "file=@/path/to/product.jpg"
```

## Configuration

Gemini uses Vertex/ADC-style configuration:

- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `GEMINI_MODEL`

Optional MLflow tracking settings:

- `MLFLOW_TRACKING_URI`
- `MLFLOW_TRACKING_ENABLED`
- `MLFLOW_EXPERIMENT_NAME`
- `MLFLOW_ARTIFACT_URI`

## Tests

```bash
uv run pytest product_analyzer/tests -q
```
