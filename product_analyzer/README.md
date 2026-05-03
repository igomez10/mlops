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
├── tracking.py         # track_run() — MLflow run-per-request, best-effort
├── evaluation.py       # evaluate() — 6 quality checks + eval_score
├── tests/              # pytest suite (23 tests)
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
# (optional) uncomment the MLFLOW_* lines to enable MLflow tracking — see below
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

## MLflow tracking + evaluation

Every `/analyze-product-image` request opens **one MLflow run** capturing what
the call did and how good the response was. Tracking is best-effort: if MLflow
is down or `MLFLOW_TRACKING_URI` is unset, the request still returns normally
and just logs a warning.

We currently use one Gemini model, so MLflow is mainly used to track prompt
iterations, latency, parse success/failure, image-level issues, and regressions
over time.

### What gets logged per run

**Params** (set once, before the Gemini call):
- `model` — Gemini model name (recorded for completeness; we pin one model for now)
- `mime` — `image/jpeg` or `image/png`
- `image_size_bytes` — uploaded image size
- `prompt_hash` — `sha256(PROMPT)[:12]`. Change the prompt → new hash → easy
  filter in the MLflow UI to compare prompt iterations
- `media_resolution` — `media_resolution_high`

**Metrics**:
- `latency_seconds` — Gemini API round-trip
- `wall_time_seconds` — total time inside the run
- `prompt_tokens`, `response_tokens`, `total_tokens` — pulled from
  `response.usage_metadata` if the SDK returned them
- `parse_ok` — 1.0 if parsing succeeded, 0.0 otherwise
- `parsed_confidence_score` — Gemini's self-reported `confidence` field
- **Eval metrics** (six 0/1 checks + an aggregate, see [`evaluation.py`](./evaluation.py)):
  - `eval_valid_json`, `eval_has_product_name`, `eval_has_brand`,
    `eval_has_category`, `eval_has_price`, `eval_price_valid_range`
  - `eval_score` — mean of the six (0.0 to 1.0). Single comparable number for
    "how complete and well-formed was this response"

**Artifacts**:
- `prompt.txt` — the full prompt sent to Gemini
- `raw_gemini_response.txt` — Gemini's raw text (logged even on parse failure)
- `parsed_output.json` — the validated structured response (only on parse success)
- `input_image.<jpg|png>` — the uploaded image

### What `eval_score` actually means

It's a completeness/format check, not a correctness check. A high score means
the response had valid JSON, all the key fields filled in, and a sensible
price range. A low score means Gemini left fields blank or returned malformed
data. Use it to:

- spot regressions ("did our changes break the output shape?")
- compare prompt iterations ("does prompt B leave fewer fields blank than prompt A?")

It does NOT measure whether the answer is *right*. A confident hallucination
that fills in every field will score 1.0. Real accuracy needs labeled ground
truth, which is a follow-up.

### Enable tracking locally

Add these lines to your `product_analyzer/.env`:

```
MLFLOW_TRACKING_URI=http://127.0.0.1:5001
MLFLOW_EXPERIMENT_NAME=product-analyzer
MLFLOW_TRACKING_ENABLED=1
MLFLOW_ARTIFACT_URI=mlflow-artifacts:/
```

Then start MLflow + restart the analyzer:

```bash
# from mlops/
make compose-up-dev   # starts MLflow on http://127.0.0.1:5001
# Ctrl+C uvicorn and re-run it so the new env vars get picked up
uvicorn product_analyzer.app:app --reload --port 8001
```

Send a request, then open `http://127.0.0.1:5001` and find your experiment.

### Heads-up: `MLFLOW_ARTIFACT_URI` gotcha

The `mlflow` Docker container's default artifact root is `/mlflow/artifacts`,
which doesn't exist as a writable path on your host. Without
`MLFLOW_ARTIFACT_URI=mlflow-artifacts:/`, params and metrics still log fine but
artifact uploads fail with `Read-only file system: '/mlflow'` warnings.

Setting `MLFLOW_ARTIFACT_URI=mlflow-artifacts:/` routes artifacts through
MLflow's `--serve-artifacts` proxy instead of trying to write directly to disk.
The tracker only applies this on **first creation** of an experiment — if you
already created one with the broken default, either:
- rename via `MLFLOW_EXPERIMENT_NAME=product-analyzer-v2`, or
- hard-delete the old experiment (UI delete is a soft-delete; use
  `mlflow gc` against the backend to purge)

### Comparing prompt iterations

This is the main A/B we can run today. Things worth iterating on:

- stricter confidence wording (e.g. "set confidence to 0.0 if any field is uncertain")
- different field guidance (e.g. tighter rules for `condition_estimate`)
- different output JSON instructions (e.g. forbidding markdown fences explicitly)

How to compare two prompts:

1. Send N images through with the current prompt → N runs in MLflow
2. Edit [`prompt.py`](./prompt.py) → `prompt_hash` changes automatically
3. Restart uvicorn, send the same N images → N more runs with the new hash
4. In the MLflow UI, group/filter by `params.prompt_hash` and compare average
   `eval_score` and `parse_ok`

### Comparing image types

Even with one prompt, you can characterize where Gemini struggles by sending
different categories of images and looking at `eval_score` per group:

- clear, well-lit photos vs blurry / low-light
- products with visible labels and model numbers vs no visible text
- packaged/new vs used/worn condition

There's no automatic grouping for this — tag the runs yourself (e.g. by
sending images in batches and noting timestamps), or split into separate
MLflow experiments per image type.

## Using the analyzer from `server.py`

The Gemini + MLflow logic lives in two functions in
[`service.py`](./service.py):

- `analyze_product_image(upload, ...)` — the FastAPI route entrypoint; takes
  an `UploadFile`, validates it, then delegates to the bytes function below.
- `analyze_product_image_bytes(image_bytes, mime_type, *, filename=None, ...)`
  — the **shared** entrypoint for callers that already hold raw bytes.

`server.py POST /posts` imports the bytes function and calls it for the first
JPEG/PNG upload only (one Gemini call → one MLflow run/trace per request).
The call is wrapped in a try/except: if Gemini or MLflow fails the post is
still created with `analysis=None`. The result, when present, is persisted on
the `Post` (`analysis: dict | None`) and returned on the `PostResponse`.

```python
# server.py — abbreviated
from product_analyzer.service import analyze_product_image_bytes

analysis_result: dict | None = None
try:
    parsed = await analyze_product_image_bytes(image_bytes, image_mime)
    analysis_result = parsed.model_dump(mode="json")
except Exception as exc:
    log.warning("product analysis skipped for post %s: %s", post_id, exc)

post = repo.create(..., analysis=analysis_result)
```

### Tracing (Traces tab)

Each request also opens one MLflow **span** around the Gemini call so it shows
up in the Traces tab with inputs, outputs, latency, and attributes
(`prompt_hash`, model name, MIME type, media resolution, `parse_ok`, output
summary). Raw image bytes are not included. Tracing is best-effort — if MLflow
is unreachable, the request still succeeds.

### Tests

```bash
pytest product_analyzer/tests/ -q
```

23 tests covering the tracker (no-op + failure paths), the eval function
(happy path + edge cases), and the full service flow with a mocked MLflow.

Unit tests use mocks: both `call_gemini` and `mlflow` are stubbed, so tests
never hit the real Gemini API or a real MLflow server. A green test run only
proves the orchestration glue works.

To verify the real integration end-to-end you need:

1. A real `GEMINI_API_KEY` in `product_analyzer/.env` — the request actually
   hits Google's Gemini API and uses your quota.
2. The `MLFLOW_*` vars set so the server can reach a live MLflow instance.
3. A real product image to POST.

```bash
curl -X POST http://127.0.0.1:8001/analyze-product-image \
  -F "file=@product_analyzer/test_image.jpg"
```

When this succeeds you should see, in the MLflow UI:

- a new **run** under the `product-analyzer` experiment with the params,
  metrics, and artifacts described above, and
- if tracing is enabled, a matching **trace** in the Traces tab with the
  `gemini.generate_content` span.

## Error handling

| Status | When                                                                  |
| ------ | --------------------------------------------------------------------- |
| 400    | Wrong MIME type, empty file, or file larger than 12 MB                |
| 422    | `file` form field missing (FastAPI default)                           |
| 502    | Gemini API call failed, or response wasn't valid JSON / right schema  |
| 503    | `GEMINI_API_KEY` not set in the environment                           |
