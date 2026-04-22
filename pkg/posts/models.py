from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Post:
    """Persistent post record."""

    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
