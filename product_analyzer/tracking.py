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
    for name, body in rec.image_artifacts.items():
        try:
            from PIL import Image

            mlflow.log_image(Image.open(BytesIO(body)), name)
        except Exception as exc:  # noqa: BLE001
            log.warning("log_image %s failed: %s", name, exc)
