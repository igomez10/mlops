from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass(frozen=True)
class CloudSettings:
    """Configuration from the process environment (Twelve-Factor App: config in env)."""

    gcp_project_id: str | None
    gcs_bucket: str | None
    firestore_database_id: str
    gemini_model: str
    gemini_api_key: str | None
    gemini_use_vertex: bool
    vertex_location: str
    mongodb_uri: str | None

    @classmethod
    def from_env(cls) -> CloudSettings:
        project = (
            _env("GOOGLE_CLOUD_PROJECT")
            or _env("GCP_PROJECT")
            or _env("GCLOUD_PROJECT")
        )
        return cls(
            gcp_project_id=project,
            gcs_bucket=_env("GCS_BUCKET"),
            firestore_database_id=_env("FIRESTORE_DATABASE_ID") or "(default)",
            gemini_model=_env("GEMINI_MODEL") or "gemini-2.0-flash",
            gemini_api_key=_env("GEMINI_API_KEY"),
            gemini_use_vertex=_env_bool("GEMINI_USE_VERTEX"),
            vertex_location=_env("GOOGLE_CLOUD_LOCATION") or "us-central1",
            mongodb_uri=_env("MONGODB_URI"),
        )
