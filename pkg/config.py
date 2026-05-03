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
    # GCS_IMAGES_BUCKET: post image uploads (e.g. mlops-images). If unset, uploads are disabled.
    gcs_images_bucket: str | None
    firestore_database_id: str
    gemini_model: str
    vertex_location: str
    mongodb_uri: str | None = None
    posts_backend: str = "auto"
    ebay_app_id: str | None = None
    ebay_cert_id: str | None = None
    ebay_sandbox: bool = False
    ebay_runame: str | None = None

    @classmethod
    def from_env(cls) -> CloudSettings:
        project = _env("GOOGLE_CLOUD_PROJECT") or _env("GCP_PROJECT") or _env("GCLOUD_PROJECT")
        return cls(
            gcp_project_id=project,
            gcs_bucket=_env("GCS_BUCKET"),
            gcs_images_bucket=_env("GCS_IMAGES_BUCKET"),
            firestore_database_id=_env("FIRESTORE_DATABASE_ID") or "(default)",
            gemini_model=_env("GEMINI_MODEL") or "gemini-2.0-flash",
            vertex_location=_env("GOOGLE_CLOUD_LOCATION") or "us-central1",
            mongodb_uri=_env("MONGODB_URI"),
            posts_backend=(_env("POSTS_BACKEND") or "auto").strip().lower(),
            ebay_app_id=_env("EBAY_APP_ID"),
            ebay_cert_id=_env("EBAY_CERT_ID"),
            ebay_sandbox=_env_bool("EBAY_SANDBOX", default=False),
            ebay_runame=_env("EBAY_RUNAME") or _env("EBAY_REDIRECT_URI"),
        )
