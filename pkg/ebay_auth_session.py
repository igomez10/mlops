from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from fastapi import Request, Response


EBAY_SESSION_COOKIE_NAME = "mlops_ebay_session"


@dataclass(frozen=True, slots=True)
class EbayAuthSession:
    user_id: str
    is_new: bool = False


class EbayAuthSessionManager:
    """Issue and validate the signed browser cookie used to identify an eBay user session."""

    def __init__(self, secret: str, *, cookie_name: str = EBAY_SESSION_COOKIE_NAME) -> None:
        if not secret:
            raise ValueError("secret is required")
        self._secret = secret
        self._cookie_name = cookie_name

    @property
    def cookie_name(self) -> str:
        return self._cookie_name

    def get_session(self, request: Request) -> EbayAuthSession | None:
        raw_cookie = request.cookies.get(self._cookie_name)
        if not raw_cookie:
            return None
        user_id = self._decode_user_id(raw_cookie)
        if not user_id:
            return None
        return EbayAuthSession(user_id=user_id, is_new=False)

    def get_or_create_session(self, request: Request) -> EbayAuthSession:
        existing = self.get_session(request)
        if existing is not None:
            return existing
        return EbayAuthSession(user_id=self._new_user_id(), is_new=True)

    def attach_session_cookie(self, response: Response, *, user_id: str, secure: bool) -> None:
        response.set_cookie(
            key=self._cookie_name,
            value=self.serialize_session_cookie(user_id),
            httponly=True,
            samesite="lax",
            secure=secure,
            max_age=60 * 60 * 24 * 365,
            path="/",
        )

    def serialize_session_cookie(self, user_id: str) -> str:
        return self._encode_user_id(user_id)

    def _new_user_id(self) -> str:
        return uuid.uuid4().hex

    def _encode_user_id(self, user_id: str) -> str:
        payload = base64.urlsafe_b64encode(
            json.dumps({"user_id": user_id}, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        signature = hmac.new(
            self._secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{signature}"

    def _decode_user_id(self, cookie_value: str) -> str | None:
        try:
            payload, signature = cookie_value.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.new(
            self._secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padding = "=" * (-len(payload) % 4)
        try:
            decoded = json.loads(base64.urlsafe_b64decode(f"{payload}{padding}"))
        except (ValueError, json.JSONDecodeError, TypeError):
            return None
        user_id = decoded.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        return user_id
