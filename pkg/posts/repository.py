from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from pkg.posts.models import Post


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("name must be non-empty")
    return cleaned


@runtime_checkable
class PostRepository(Protocol):
    """Storage port for posts (swap implementations: memory, MongoDB, etc.)."""

    def get_by_id(self, post_id: str, *, include_deleted: bool = False) -> Post | None:
        """Return the post with this id, or ``None``."""

    def get_by_name(self, name: str, *, include_deleted: bool = False) -> Post | None:
        """Return the post with this name (exact match after strip), or ``None``."""

    def list_posts(self, *, include_deleted: bool = False) -> list[Post]:
        """Return posts, typically ordered by ``created_at`` ascending."""

    def create(self, name: str) -> Post:
        """Create a post; raises ``ValueError`` if ``name`` is invalid or not unique among active posts."""

    def update(self, post_id: str, *, name: str) -> Post | None:
        """
        Update an active post's name and ``updated_at``.

        Returns ``None`` if no active post exists for ``post_id``.
        Raises ``ValueError`` if ``name`` is invalid or would duplicate another active post.
        """

    def soft_delete(self, post_id: str) -> Post | None:
        """Set ``deleted_at`` / ``updated_at`` if the post exists and is not already deleted."""


class InMemoryPostRepository:
    """Process-local store keyed by id with a secondary index on normalized name (active posts only)."""

    def __init__(self) -> None:
        self._by_id: dict[str, Post] = {}
        self._id_by_normalized_name: dict[str, str] = {}

    def get_by_id(self, post_id: str, *, include_deleted: bool = False) -> Post | None:
        post = self._by_id.get(post_id)
        if post is None:
            return None
        if not include_deleted and post.deleted_at is not None:
            return None
        return post

    def get_by_name(self, name: str, *, include_deleted: bool = False) -> Post | None:
        try:
            key = _normalize_name(name)
        except ValueError:
            return None
        if not include_deleted:
            post_id = self._id_by_normalized_name.get(key)
            if post_id is None:
                return None
            return self.get_by_id(post_id, include_deleted=False)
        matches = [p for p in self._by_id.values() if p.name == key]
        if not matches:
            return None
        return max(matches, key=lambda p: p.created_at)

    def list_posts(self, *, include_deleted: bool = False) -> list[Post]:
        posts = list(self._by_id.values())
        if not include_deleted:
            posts = [p for p in posts if p.deleted_at is None]
        return sorted(posts, key=lambda p: p.created_at)

    def create(self, name: str) -> Post:
        key = _normalize_name(name)
        if key in self._id_by_normalized_name:
            raise ValueError(f"a post with name {key!r} already exists")

        now = _utc_now()
        post = Post(
            id=str(uuid.uuid4()),
            name=key,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self._by_id[post.id] = post
        self._id_by_normalized_name[key] = post.id
        return post

    def update(self, post_id: str, *, name: str) -> Post | None:
        post = self.get_by_id(post_id, include_deleted=False)
        if post is None:
            return None

        new_key = _normalize_name(name)
        old_key = post.name
        if new_key != old_key:
            if new_key in self._id_by_normalized_name:
                raise ValueError(f"a post with name {new_key!r} already exists")
            del self._id_by_normalized_name[old_key]
            self._id_by_normalized_name[new_key] = post_id

        post.name = new_key
        post.updated_at = _utc_now()
        return post

    def soft_delete(self, post_id: str) -> Post | None:
        post = self.get_by_id(post_id, include_deleted=True)
        if post is None or post.deleted_at is not None:
            return None
        old_key = post.name
        now = _utc_now()
        post.deleted_at = now
        post.updated_at = now
        del self._id_by_normalized_name[old_key]
        return post
