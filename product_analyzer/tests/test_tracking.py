from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from product_analyzer.gemini_vision import _extract_usage
from product_analyzer.tracking import RunRecorder, prompt_hash, track_run


# --- _enabled / no-op behavior --------------------------------------------------


def test_no_op_when_uri_unset(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    fake_mlflow = MagicMock()
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    with track_run() as rec:
        rec.set_param("model", "x")

    fake_mlflow.start_run.assert_not_called()
    fake_mlflow.set_tracking_uri.assert_not_called()


def test_no_op_when_disabled_flag(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://fake:5000")
    monkeypatch.setenv("MLFLOW_TRACKING_ENABLED", "0")
    fake_mlflow = MagicMock()
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    with track_run() as rec:
        rec.set_metric("x", 1.0)

    fake_mlflow.start_run.assert_not_called()


# --- failure swallowing ---------------------------------------------------------


def test_setup_failure_is_swallowed(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://fake:5000")
    fake_mlflow = MagicMock()
    fake_mlflow.set_tracking_uri.side_effect = RuntimeError("boom")
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    with track_run() as rec:
        rec.set_param("k", "v")

    fake_mlflow.start_run.assert_not_called()


def test_start_run_failure_is_swallowed(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://fake:5000")
    fake_mlflow = MagicMock()
    fake_mlflow.start_run.side_effect = RuntimeError("server unreachable")
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    with track_run() as rec:
        rec.set_param("k", "v")

    fake_mlflow.start_run.assert_called_once()


def test_per_metric_failure_does_not_break_flush(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://fake:5000")
    fake_mlflow = MagicMock()
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    raised = {"once": False}

    def log_metric(key, value):
        if not raised["once"] and key == "a":
            raised["once"] = True
            raise RuntimeError("nope")

    fake_mlflow.log_metric.side_effect = log_metric

    with track_run() as rec:
        rec.set_metric("a", 1.0)
        rec.set_metric("b", 2.0)

    keys = [c.args[0] for c in fake_mlflow.log_metric.call_args_list]
    assert "a" in keys and "b" in keys


# --- happy path: everything is forwarded ---------------------------------------


def test_happy_path_flushes_params_metrics_text_image(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://fake:5000")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "test-exp")
    fake_mlflow = MagicMock()
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)

    # Avoid pulling in real PIL — make sure log_image is callable but never errors.
    fake_pil_module = MagicMock()
    fake_pil_module.Image.open.return_value = MagicMock()
    monkeypatch.setitem(sys.modules, "PIL", fake_pil_module)

    with track_run("my-run") as rec:
        rec.set_param("model", "gemini-3.1")
        rec.set_metric("latency_seconds", 0.5)
        rec.set_text("prompt.txt", "hello")
        rec.set_image("input_image.jpg", b"\xff\xd8\xff")

    fake_mlflow.set_tracking_uri.assert_called_once_with("http://fake:5000")
    fake_mlflow.set_experiment.assert_called_once_with("test-exp")
    fake_mlflow.start_run.assert_called_once_with(run_name="my-run")

    fake_mlflow.log_param.assert_any_call("model", "gemini-3.1")
    metric_keys = {c.args[0] for c in fake_mlflow.log_metric.call_args_list}
    assert "latency_seconds" in metric_keys
    assert "wall_time_seconds" in metric_keys

    fake_mlflow.log_text.assert_called_once_with("hello", "prompt.txt")
    fake_mlflow.log_image.assert_called_once()
    assert fake_mlflow.log_image.call_args.args[1] == "input_image.jpg"


# --- helpers --------------------------------------------------------------------


def test_prompt_hash_stable_and_truncated():
    h1 = prompt_hash("hello")
    h2 = prompt_hash("hello")
    h3 = prompt_hash("hello!")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 12


def test_extract_usage_handles_missing_metadata():
    response = SimpleNamespace()
    assert _extract_usage(response) == {}


def test_extract_usage_partial_fields():
    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=None,
            total_token_count=10,
        )
    )
    assert _extract_usage(response) == {"prompt_tokens": 10.0, "total_tokens": 10.0}


def test_run_recorder_update_metrics_coerces_to_float():
    rec = RunRecorder()
    rec.update_metrics({"a": 1, "b": 2.5})
    assert rec.metrics == {"a": 1.0, "b": 2.5}
    assert isinstance(rec.metrics["a"], float)


# --- isolation -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip MLflow env vars between tests so leakage can't mask no-op cases."""
    for name in ("MLFLOW_TRACKING_URI", "MLFLOW_EXPERIMENT_NAME", "MLFLOW_TRACKING_ENABLED"):
        monkeypatch.delenv(name, raising=False)
