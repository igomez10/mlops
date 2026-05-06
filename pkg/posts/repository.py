from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from pkg.logging_context import get_logger
from pkg.posts.models import Listing, Post

log = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("name must be non-empty")
    return cleaned


def _synthetic_listings_for_new_post(caption: str, image_urls: list[str], now: datetime) -> list[Listing]:
    """Server-generated draft listings, one per uploaded image (no user-provided fields)."""
    cap = caption if caption else "post"
    return [
        Listing(
            id=str(uuid.uuid4()),
            marketplace_url=f"https://local.invalid/pending?i={i}",
            image_url=url,
            created_at=now,
            status="draft",
            description=f"Pending marketplace link (image {i + 1}, {cap})",
        )
        for i, url in enumerate(image_urls)
    ]


@runtime_checkable
class PostRepository(Protocol):
    """Storage port for posts (swap implementations: memory, MongoDB, etc.)."""

    def get_by_id(self, post_id: str, *, include_deleted: bool = False) -> Post | None:
        """Return the post with this id, or ``None``."""

    def get_by_name(self, name: str, *, include_deleted: bool = False) -> Post | None:
        """Return the post with this name (exact match after strip), or ``None``."""

    def list_posts(self, *, include_deleted: bool = False) -> list[Post]:
        """Return posts, typically ordered by ``created_at`` ascending."""

    def create(
        self,
        name: str,
        *,
        description: str = "",
        post_id: str | None = None,
        image_urls: list[str] | None = None,
        analysis: dict | None = None,
        listings: list[Listing] | None = None,
    ) -> Post:
        """
        Create a post.

        If ``post_id`` is set (e.g. after uploading images to storage under that
        id), the new post uses that id; otherwise an id is generated.
        ``analysis`` is an optional opaque dict (e.g. Gemini product analysis)
        stored verbatim on the post. If ``listings`` is omitted, default draft
        listings are derived from ``image_urls``. Raises ``ValueError`` if the name is
        invalid or not unique among active posts.
        """

    def update(
        self,
        post_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Post | None:
        """
        Update an active post's name and/or description. At least one of ``name`` or
        ``description`` must be provided.

        Returns ``None`` if no active post exists for ``post_id``.
        Raises ``ValueError`` if a field is invalid or a new name would duplicate another active post.
        """

    def soft_delete(self, post_id: str) -> Post | None:
        """Set ``deleted_at`` / ``updated_at`` if the post exists and is not already deleted."""

    def replace_listings(self, post_id: str, listings: list[Listing]) -> Post | None:
        """Replace a post's embedded marketplace listings."""

    def set_ebay_draft(self, post_id: str, draft: dict | None) -> Post | None:
        """Store (or clear) the eBay listing draft on the post."""


class InMemoryPostRepository:
    """Process-local store keyed by id with a secondary index on normalized name (active posts only)."""

    def __init__(self) -> None:
        self._by_id: dict[str, Post] = {}
        self._id_by_normalized_name: dict[str, str] = {}

    def get_by_id(self, post_id: str, *, include_deleted: bool = False) -> Post | None:
        log.info("InMemoryPostRepository.get_by_id post_id=%s include_deleted=%s", post_id, include_deleted)
        post = self._by_id.get(post_id)
        if post is None:
            return None
        if not include_deleted and post.deleted_at is not None:
            return None
        return post

    def get_by_name(self, name: str, *, include_deleted: bool = False) -> Post | None:
        log.info("InMemoryPostRepository.get_by_name name=%s include_deleted=%s", name, include_deleted)
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
        log.info("InMemoryPostRepository.list_posts include_deleted=%s", include_deleted)
        posts = list(self._by_id.values())
        if not include_deleted:
            posts = [p for p in posts if p.deleted_at is None]
        return sorted(posts, key=lambda p: p.created_at)

    def create(
        self,
        name: str,
        *,
        description: str = "",
        post_id: str | None = None,
        image_urls: list[str] | None = None,
        analysis: dict | None = None,
        listings: list[Listing] | None = None,
    ) -> Post:
        log.info(
            "InMemoryPostRepository.create name=%s post_id=%s image_count=%d analysis_present=%s",
            name,
            post_id,
            len(image_urls or []),
            analysis is not None,
        )
        key = _normalize_name(name)
        if key in self._id_by_normalized_name:
            raise ValueError(f"a post with name {key!r} already exists")

        urls = list(image_urls) if image_urls is not None else []
        now = _utc_now()
        pid = post_id or str(uuid.uuid4())
        desc = description.strip() if description else ""
        list_caption = desc or key
        resolved_listings = (
            list(listings) if listings is not None else _synthetic_listings_for_new_post(list_caption, urls, now)
        )
        post = Post(
            id=pid,
            name=key,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            description=desc,
            listings=resolved_listings,
            image_urls=urls,
            analysis=analysis,
            ebay_draft=None,
        )
        self._by_id[post.id] = post
        self._id_by_normalized_name[key] = post.id
        return post

    def update(
        self,
        post_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Post | None:
        log.info(
            "InMemoryPostRepository.update post_id=%s name_present=%s description_present=%s",
            post_id,
            name is not None,
            description is not None,
        )
        post = self.get_by_id(post_id, include_deleted=False)
        if post is None:
            return None
        if name is None and description is None:
            raise ValueError("at least one of name or description is required")
        if name is not None:
            new_key = _normalize_name(name)
            old_key = post.name
            if new_key != old_key:
                if new_key in self._id_by_normalized_name:
                    raise ValueError(
                        f"a post with name {new_key!r} already exists",
                    )
                del self._id_by_normalized_name[old_key]
                self._id_by_normalized_name[new_key] = post_id
            post.name = new_key
        if description is not None:
            post.description = description.strip()
        post.updated_at = _utc_now()
        return post

    def soft_delete(self, post_id: str) -> Post | None:
        log.info("InMemoryPostRepository.soft_delete post_id=%s", post_id)
        post = self.get_by_id(post_id, include_deleted=True)
        if post is None or post.deleted_at is not None:
            return None
        old_key = post.name
        now = _utc_now()
        post.deleted_at = now
        post.updated_at = now
        del self._id_by_normalized_name[old_key]
        return post

    def replace_listings(self, post_id: str, listings: list[Listing]) -> Post | None:
        log.info(
            "InMemoryPostRepository.replace_listings post_id=%s listing_count=%d",
            post_id,
            len(listings),
        )
        post = self.get_by_id(post_id, include_deleted=False)
        if post is None:
            return None
        post.listings = list(listings)
        post.updated_at = _utc_now()
        return post

    def set_ebay_draft(self, post_id: str, draft: dict | None) -> Post | None:
        log.info(
            "InMemoryPostRepository.set_ebay_draft post_id=%s draft_present=%s",
            post_id,
            draft is not None,
        )
        post = self.get_by_id(post_id, include_deleted=False)
        if post is None:
            return None
        post.ebay_draft = draft
        post.updated_at = _utc_now()
        return post
