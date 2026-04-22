from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from pkg.posts.models import Post
from pkg.posts.repository import _normalize_name, _utc_now


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _doc_to_post(doc: dict[str, Any]) -> Post:
    raw_deleted = doc.get("deleted_at")
    return Post(
        id=doc["_id"],
        name=doc["name"],
        created_at=_ensure_utc(doc["created_at"]),
        updated_at=_ensure_utc(doc["updated_at"]),
        deleted_at=_ensure_utc(raw_deleted) if raw_deleted is not None else None,
    )


class MongoPostRepository:
    """MongoDB-backed store: unique ``name`` among active posts (``deleted_at`` is null)."""

    def __init__(self, collection: Collection) -> None:
        self._coll = collection
        self._coll.create_index(
            [("name", ASCENDING)],
            unique=True,
            partialFilterExpression={"deleted_at": None},
        )

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
            cur = self._coll.find({"name": key}).sort([("created_at", -1)]).limit(1)
            doc = next(cur, None)
        return _doc_to_post(doc) if doc else None

    def list_posts(self, *, include_deleted: bool = False) -> list[Post]:
        query: dict[str, Any] = {} if include_deleted else {"deleted_at": None}
        cursor = self._coll.find(query).sort("created_at", ASCENDING)
        return [_doc_to_post(doc) for doc in cursor]

    def create(self, name: str) -> Post:
        key = _normalize_name(name)
        now = _utc_now()
        post_id = str(uuid.uuid4())
        doc = {
            "_id": post_id,
            "name": key,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        try:
            self._coll.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ValueError(f"a post with name {key!r} already exists") from exc
        return _doc_to_post(doc)

    def update(self, post_id: str, *, name: str) -> Post | None:
        new_key = _normalize_name(name)
        if self._coll.find_one({"_id": post_id, "deleted_at": None}) is None:
            return None
        try:
            res = self._coll.update_one(
                {"_id": post_id, "deleted_at": None},
                {"$set": {"name": new_key, "updated_at": _utc_now()}},
            )
        except DuplicateKeyError as exc:
            raise ValueError(f"a post with name {new_key!r} already exists") from exc
        if res.matched_count == 0:
            return None
        doc = self._coll.find_one({"_id": post_id})
        assert doc is not None
        return _doc_to_post(doc)

    def soft_delete(self, post_id: str) -> Post | None:
        now = _utc_now()
        if self._coll.find_one({"_id": post_id, "deleted_at": None}) is None:
            return None
        self._coll.update_one(
            {"_id": post_id},
            {"$set": {"deleted_at": now, "updated_at": now}},
        )
        doc = self._coll.find_one({"_id": post_id})
        return _doc_to_post(doc) if doc else None
