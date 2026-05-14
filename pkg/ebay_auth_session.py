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
    """Signed cookie manager for lightweight eBay auth sessions."""

    cookie_name = "mlops_ebay_session"

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("secret is required")
        self._secret = secret.encode()

    def serialize_session_cookie(self, user_id: str) -> str:
        payload = {"user_id": user_id}
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        signature = hmac.new(self._secret, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def get_session(self, request: Request) -> EbayAuthSession | None:
        raw = request.cookies.get(self.cookie_name)
        if not raw:
            return None
        try:
            encoded, signature = raw.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.new(self._secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        try:
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(f"{encoded}{padding}"))
            user_id = str(payload["user_id"]).strip()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not user_id:
            return None
        return EbayAuthSession(user_id=user_id)

    def get_or_create_session(self, request: Request) -> EbayAuthSession:
        session = self.get_session(request)
        if session is not None:
            return session
        return EbayAuthSession(user_id=uuid.uuid4().hex)

    def attach_session_cookie(
        self,
        response: Response,
        *,
        user_id: str,
        secure: bool,
    ) -> None:
        response.set_cookie(
            self.cookie_name,
            self.serialize_session_cookie(user_id),
            httponly=True,
            samesite="lax",
            secure=secure,
            path="/",
        )
