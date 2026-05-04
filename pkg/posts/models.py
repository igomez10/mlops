from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Listing:
    """A listing resource embedded in a post document."""

    id: str
    marketplace_url: str
    image_url: str
    created_at: datetime
    status: str
    description: str


@dataclass(slots=True)
class Post:
    """Persistent post record; listings and image URLs live in the same document."""

    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    description: str = ""
    listings: list[Listing] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    # Optional Gemini product analysis attached at create time. Opaque dict so
    # the post layer doesn't depend on the analyzer schema.
    analysis: dict | None = None
    # Draft eBay listing (category, title, item specifics, etc.) awaiting user review.
    ebay_draft: dict | None = None
