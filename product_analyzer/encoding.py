# niki
from __future__ import annotations

import base64


def image_to_base64(data: bytes) -> str:
    """Base64-encode raw image bytes to an ASCII string.

    The google-genai SDK accepts raw bytes via Part.from_bytes and handles wire
    encoding itself. This helper is kept as a standalone utility so callers that
    need the base64 form (logging, custom HTTP calls, tests) can get it.
    """
    return base64.b64encode(data).decode("ascii")
