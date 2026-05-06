"""Request-scoped logging context.

Threads/tasks each have their own ``request_id``: a ``ContextVar`` is the
right primitive — it survives ``await`` boundaries inside one request without
leaking across concurrent requests. Every log record gets the current
request id injected so downstream operators can correlate logs from the
network, controller, and storage layers for the same HTTP call.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextvars import ContextVar, Token

REQUEST_ID_HEADER = "X-Request-Id"
_NO_REQUEST_ID = "-"

_request_id_var: ContextVar[str] = ContextVar("request_id", default=_NO_REQUEST_ID)


def get_request_id() -> str:
    """Return the current request id, or ``"-"`` if none is set."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> Token[str]:
    """Bind ``request_id`` to the current context. Returns a reset token."""
    return _request_id_var.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id_var.reset(token)


def new_request_id() -> str:
    """Generate a fresh request id."""
    return uuid.uuid4().hex


class RequestIdFilter(logging.Filter):
    """Injects ``request_id`` onto every log record so formatters can render it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


_DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
_configured = False


def configure_logging(level: int | str | None = None) -> None:
    """Idempotent root-logger setup that includes ``request_id`` in every line.

    Safe to call from multiple entry points (FastAPI lifespan, CLI scripts).
    """
    global _configured
    if _configured:
        return

    resolved_level = level if level is not None else os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    root.setLevel(resolved_level)

    request_id_filter = RequestIdFilter()

    if not root.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        stream_handler.addFilter(request_id_filter)
        root.addHandler(stream_handler)
    else:
        for existing in root.handlers:
            if not any(isinstance(f, RequestIdFilter) for f in existing.filters):
                existing.addFilter(request_id_filter)
            if existing.formatter is None:
                existing.setFormatter(logging.Formatter(_DEFAULT_FORMAT))

    # Uvicorn pre-configures its own loggers; make them inherit our handler
    # so request_id appears in access logs too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.addFilter(request_id_filter)

    _configured = True


def get_logger(name: str) -> logging.LoggerAdapter:
    """Return a logger that carries the current request id in ``extra``.

    LoggerAdapter ensures that calls to ``log.info(msg, extra={...})`` still
    work — the adapter merges callers' extras over the request_id binding.
    """
    base = logging.getLogger(name)

    class _RequestIdAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            extra = kwargs.get("extra") or {}
            merged = {"request_id": get_request_id(), **extra}
            kwargs["extra"] = merged
            return msg, kwargs

    return _RequestIdAdapter(base, {})


__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIdFilter",
    "configure_logging",
    "get_logger",
    "get_request_id",
    "new_request_id",
    "reset_request_id",
    "set_request_id",
]
