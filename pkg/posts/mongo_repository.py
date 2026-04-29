from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from pkg.posts.models import Listing, Post
from pkg.posts.repository import (
    _normalize_name,
    _synthetic_listings_for_new_post,
    _utc_now,
)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _raw_listing_to_listing(raw: dict[str, Any]) -> Listing:
    """Load listing; support legacy docs that only stored ``title``."""
    if "title" in raw and "marketplace_url" not in raw:
        return Listing(
            id=raw["id"],
            marketplace_url="",
            image_url="",
            created_at=_ensure_utc(raw["created_at"]),
            status="legacy",
            description=(raw.get("title") or "").strip(),
        )
    return Listing(
        id=raw["id"],
        marketplace_url=str(raw.get("marketplace_url") or ""),
        image_url=str(raw.get("image_url") or ""),
        created_at=_ensure_utc(raw["created_at"]),
        status=str(raw.get("status") or ""),
        description=str(raw.get("description") or ""),
    )


def _doc_to_post(doc: dict[str, Any]) -> Post:
    raw_deleted = doc.get("deleted_at")
    raw_listings = doc.get("listings")
    if raw_listings is None:
        listings: list[Listing] = []
    else:
        listings = [_raw_listing_to_listing(x) for x in raw_listings]
    raw_images = doc.get("image_urls")
    image_urls = [str(u) for u in raw_images] if raw_images else []
    raw_desc = doc.get("description")
    return Post(
        id=doc["_id"],
        name=doc["name"],
        created_at=_ensure_utc(doc["created_at"]),
        updated_at=_ensure_utc(doc["updated_at"]),
        deleted_at=_ensure_utc(raw_deleted) if raw_deleted is not None else None,
        description=str(raw_desc) if raw_desc is not None else "",
        listings=listings,
        image_urls=image_urls,
    )


class MongoPostRepository:
    """MongoDB-backed store: unique ``name`` among active posts (``deleted_at`` is null)."""

    def __init__(self, collection: Any) -> None:
        self._coll = collection
        create_index = getattr(self._coll, "create_index", None)
        if callable(create_index):
            create_index(
                [("name", ASCENDING)],
                unique=True,
                partialFilterExpression={"deleted_at": None},
            )

    def _find(self, query: dict[str, Any], *, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._coll.find(query, limit=limit)
        if isinstance(rows, list):
            return rows
        return list(rows)

    def _has_active_name_conflict(
        self,
        normalized_name: str,
        *,
        exclude_post_id: str | None = None,
    ) -> bool:
        for doc in self._find({"name": normalized_name, "deleted_at": None}):
            if exclude_post_id is None or doc.get("_id") != exclude_post_id:
                return True
        return False

    def get_by_id(self, post_id: str, *, include_deleted: bool = False) -> Post | None:
        doc = self._coll.find_one({"_id": post_id})
        if doc is None:
            return None
        post = _doc_to_post(doc)
        if not include_deleted and post.deleted_at is not None:
            return None
        return post

    def get_by_name(self, name: str, *, include_deleted: bool = False) -> Post | None:
        try:
            key = _normalize_name(name)
        except ValueError:
            return None
        if not include_deleted:
            doc = self._coll.find_one({"name": key, "deleted_at": None})
        else:
            matches = self._find({"name": key})
            doc = max(matches, key=lambda d: _ensure_utc(d["created_at"]), default=None)
        return _doc_to_post(doc) if doc else None

    def list_posts(self, *, include_deleted: bool = False) -> list[Post]:
        query: dict[str, Any] = {} if include_deleted else {"deleted_at": None}
        docs = self._find(query)
        docs.sort(key=lambda d: _ensure_utc(d["created_at"]))
        return [_doc_to_post(doc) for doc in docs]

    def create(
        self,
        name: str,
        *,
        description: str = "",
        post_id: str | None = None,
        image_urls: list[str] | None = None,
    ) -> Post:
        key = _normalize_name(name)
        if self._has_active_name_conflict(key):
            raise ValueError(f"a post with name {key!r} already exists")
        urls = list(image_urls) if image_urls is not None else []
        now = _utc_now()
        pid = post_id or str(uuid.uuid4())
        desc = description.strip() if description else ""
        list_caption = desc or key
        listings = _synthetic_listings_for_new_post(list_caption, urls, now)
        raw_listings = [
            {
                "id": L.id,
                "marketplace_url": L.marketplace_url,
                "image_url": L.image_url,
                "created_at": L.created_at,
                "status": L.status,
                "description": L.description,
            }
            for L in listings
        ]
        doc = {
            "_id": pid,
            "name": key,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            "description": desc,
            "listings": raw_listings,
            "image_urls": urls,
        }
        try:
            self._coll.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ValueError(f"a post with name {key!r} already exists") from exc
        return _doc_to_post(doc)

    def update(
        self,
        post_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Post | None:
        if self.get_by_id(post_id, include_deleted=False) is None:
            return None
        if name is None and description is None:
            raise ValueError("at least one of name or description is required")
        to_set: dict[str, object] = {"updated_at": _utc_now()}
        if name is not None:
            normalized_name = _normalize_name(name)
            if self._has_active_name_conflict(normalized_name, exclude_post_id=post_id):
                raise ValueError(f"a post with name {normalized_name!r} already exists")
            to_set["name"] = normalized_name
        if description is not None:
            to_set["description"] = description.strip()
        try:
            res = self._coll.update_one(
                {"_id": post_id},
                {"$set": to_set},
            )
        except DuplicateKeyError as exc:
            raise ValueError(
                f"a post with name {to_set.get('name', '')!r} already exists"
            ) from exc
        if res.matched_count == 0:
            return None
        doc = self._coll.find_one({"_id": post_id})
        assert doc is not None
        return _doc_to_post(doc)

    def soft_delete(self, post_id: str) -> Post | None:
        now = _utc_now()
        if self.get_by_id(post_id, include_deleted=False) is None:
            return None
        self._coll.update_one(
            {"_id": post_id},
            {"$set": {"deleted_at": now, "updated_at": now}},
        )
        doc = self._coll.find_one({"_id": post_id})
        return _doc_to_post(doc) if doc else None
