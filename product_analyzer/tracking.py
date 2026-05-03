from __future__ import annotations

import hashlib
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Iterator

log = logging.getLogger(__name__)

_PROMPT_HASH_LEN = 12
_DEFAULT_EXPERIMENT = "product-analyzer"


@dataclass
class RunRecorder:
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    text_artifacts: dict[str, str] = field(default_factory=dict)
    image_artifacts: dict[str, bytes] = field(default_factory=dict)

    def set_param(self, key: str, value: Any) -> None:
        self.params[key] = value

    def set_metric(self, key: str, value: float) -> None:
        self.metrics[key] = float(value)

    def set_text(self, name: str, body: str) -> None:
        self.text_artifacts[name] = body

    def set_image(self, name: str, body: bytes) -> None:
        self.image_artifacts[name] = body

    def update_metrics(self, values: dict[str, float]) -> None:
        self.metrics.update({k: float(v) for k, v in values.items()})


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:_PROMPT_HASH_LEN]


def _enabled() -> bool:
    if os.environ.get("MLFLOW_TRACKING_ENABLED", "1") == "0":
        return False
    return bool(os.environ.get("MLFLOW_TRACKING_URI"))


@contextmanager
def track_run(run_name: str = "analyze-product-image") -> Iterator[RunRecorder]:
    rec = RunRecorder()
    if not _enabled():
        yield rec
        return

    try:
        import mlflow

        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", _DEFAULT_EXPERIMENT)
        artifact_uri = os.environ.get("MLFLOW_ARTIFACT_URI")
        # Create with explicit artifact_location so the client doesn't try to
        # write to the server's local default (e.g. /mlflow/artifacts) — which
        # is unreachable from the host. Only applies on first creation; an
        # existing experiment keeps whatever location it was created with.
        if artifact_uri and mlflow.get_experiment_by_name(experiment_name) is None:
            mlflow.create_experiment(experiment_name, artifact_location=artifact_uri)
        mlflow.set_experiment(experiment_name)
    except Exception as exc:  # noqa: BLE001
        log.warning("mlflow setup failed (%s); continuing without tracking", exc)
        yield rec
        return

    try:
        run_ctx = mlflow.start_run(run_name=run_name)
    except Exception as exc:  # noqa: BLE001
        log.warning("mlflow start_run failed (%s); continuing without tracking", exc)
        yield rec
        return

    started = time.perf_counter()
    with run_ctx:
        try:
            yield rec
        finally:
            rec.set_metric("wall_time_seconds", time.perf_counter() - started)
            try:
                _flush(mlflow, rec)
            except Exception as exc:  # noqa: BLE001
                log.warning("mlflow flush failed (%s); request unaffected", exc)


@contextmanager
def start_span(
    name: str,
    *,
    span_type: str = "LLM",
    inputs: dict[str, Any] | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Best-effort GenAI span around an LLM call.

    Yields a span-like object with `set_outputs`, `set_attributes`, and
    `record_exception` methods. If MLflow tracing is unavailable or fails,
    yields a no-op so callers stay tracing-agnostic. Exceptions raised inside
    the block are recorded on the span and re-raised.
    """
    if not _enabled():
        yield _NoopSpan()
        return

    try:
        import mlflow
    except Exception as exc:  # noqa: BLE001
        log.warning("mlflow import failed for span (%s); continuing", exc)
        yield _NoopSpan()
        return

    try:
        cm = mlflow.start_span(name=name, span_type=span_type, attributes=attributes)
    except Exception as exc:  # noqa: BLE001
        log.warning("mlflow.start_span failed (%s); continuing without span", exc)
        yield _NoopSpan()
        return

    # mlflow.start_span auto-records exceptions and sets ERROR status;
    # we let them propagate so callers can handle/transform them as before.
    with cm as span:
        try:
            if inputs is not None:
                span.set_inputs(inputs)
        except Exception as exc:  # noqa: BLE001
            log.warning("span.set_inputs failed: %s", exc)
        yield span


class _NoopSpan:
    """Stand-in span used when tracing is disabled or the SDK errors out."""

    def set_inputs(self, _: Any) -> None: ...
    def set_outputs(self, _: Any) -> None: ...
    def set_attributes(self, _: dict[str, Any]) -> None: ...
    def set_attribute(self, _key: str, _value: Any) -> None: ...
    def record_exception(self, _exc: BaseException) -> None: ...


def _flush(mlflow: Any, rec: RunRecorder) -> None:
    for k, v in rec.params.items():
        try:
            mlflow.log_param(k, v)
        except Exception as exc:  # noqa: BLE001
            log.warning("log_param %s failed: %s", k, exc)
    for k, v in rec.metrics.items():
        try:
            mlflow.log_metric(k, v)
        except Exception as exc:  # noqa: BLE001
            log.warning("log_metric %s failed: %s", k, exc)
    for name, body in rec.text_artifacts.items():
        try:
            mlflow.log_text(body, name)
        except Exception as exc:  # noqa: BLE001
            log.warning("log_text %s failed: %s", name, exc)
    for name, img_body in rec.image_artifacts.items():
        try:
            from PIL import Image

            mlflow.log_image(Image.open(BytesIO(img_body)), name)
        except Exception as exc:  # noqa: BLE001
            log.warning("log_image %s failed: %s", name, exc)
