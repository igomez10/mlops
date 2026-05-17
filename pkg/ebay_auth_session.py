from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from fastapi import Response
from starlette.requests import Request


@dataclass(frozen=True, slots=True)
class EbayAuthSession:
    user_id: str


class EbayAuthSessionManager:
    cookie_name = "mlops_ebay_session"
    _cookie_max_age_seconds = 60 * 60 * 24 * 30  # 30 days

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("secret is required")
        self._secret = secret.encode()

    def get_session(self, request: Request) -> EbayAuthSession | None:
        raw = request.cookies.get(self.cookie_name)
        if not raw:
            return None
        user_id = self._parse_session_cookie(raw)
        if not user_id:
            return None
        return EbayAuthSession(user_id=user_id)

    def get_or_create_session(self, request: Request) -> EbayAuthSession:
        existing = self.get_session(request)
        if existing is not None:
            return existing
        return EbayAuthSession(user_id=uuid.uuid4().hex)

    def attach_session_cookie(self, response: Response, *, user_id: str, secure: bool) -> None:
        response.set_cookie(
            key=self.cookie_name,
            value=self.serialize_session_cookie(user_id),
            max_age=self._cookie_max_age_seconds,
            httponly=True,
            samesite="lax",
            secure=secure,
            path="/",
        )

    def serialize_session_cookie(self, user_id: str) -> str:
        payload = base64.urlsafe_b64encode(json.dumps({"user_id": user_id}, separators=(",", ":")).encode()).decode()
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def _parse_session_cookie(self, cookie_value: str) -> str | None:
        try:
            payload, signature = cookie_value.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        try:
            data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        except (ValueError, json.JSONDecodeError):
            return None
        user_id = data.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        return user_id
