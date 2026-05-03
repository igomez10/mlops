from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(slots=True)
class EbayUserToken:
    user_id: str
    access_token: str
    refresh_token: str | None
    token_type: str
    scopes: list[str]
    expires_at: datetime
    refresh_token_expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@runtime_checkable
class EbayTokenRepository(Protocol):
    def get_by_user_id(self, user_id: str) -> EbayUserToken | None:
        """Return stored eBay OAuth tokens for this user, or ``None``."""

    def upsert(self, token: EbayUserToken) -> EbayUserToken:
        """Insert or replace stored eBay OAuth tokens for this user."""


class InMemoryEbayTokenRepository:
    def __init__(self) -> None:
        self._by_user_id: dict[str, EbayUserToken] = {}

    def get_by_user_id(self, user_id: str) -> EbayUserToken | None:
        return self._by_user_id.get(user_id)

    def upsert(self, token: EbayUserToken) -> EbayUserToken:
        self._by_user_id[token.user_id] = token
        return token


def _doc_to_token(doc: dict[str, Any]) -> EbayUserToken:
    raw_refresh_expires = doc.get("refresh_token_expires_at")
    raw_created = doc.get("created_at")
    raw_updated = doc.get("updated_at")
    return EbayUserToken(
        user_id=str(doc["user_id"]),
        access_token=str(doc["access_token"]),
        refresh_token=str(doc.get("refresh_token")) if doc.get("refresh_token") is not None else None,
        token_type=str(doc.get("token_type") or "Bearer"),
        scopes=[str(x) for x in doc.get("scopes") or []],
        expires_at=_ensure_utc(doc["expires_at"]),
        refresh_token_expires_at=(_ensure_utc(raw_refresh_expires) if raw_refresh_expires is not None else None),
        created_at=_ensure_utc(raw_created) if raw_created is not None else None,
        updated_at=_ensure_utc(raw_updated) if raw_updated is not None else None,
    )


class MongoEbayTokenRepository:
    def __init__(self, collection: Any) -> None:
        self._coll = collection
        create_index = getattr(self._coll, "create_index", None)
        if callable(create_index):
            create_index("user_id", unique=True)

    def get_by_user_id(self, user_id: str) -> EbayUserToken | None:
        doc = self._coll.find_one({"user_id": user_id})
        return _doc_to_token(doc) if doc is not None else None

    def upsert(self, token: EbayUserToken) -> EbayUserToken:
        doc = {
            "_id": token.user_id,
            "user_id": token.user_id,
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "token_type": token.token_type,
            "scopes": list(token.scopes),
            "expires_at": token.expires_at,
            "refresh_token_expires_at": token.refresh_token_expires_at,
            "created_at": token.created_at,
            "updated_at": token.updated_at,
        }
        existing = self._coll.find_one({"user_id": token.user_id})
        if existing is None:
            self._coll.insert_one(doc)
            return token
        self._coll.update_one({"user_id": token.user_id}, {"$set": doc})
        return token
