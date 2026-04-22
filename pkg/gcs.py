from __future__ import annotations

from typing import TYPE_CHECKING

from google.cloud import storage

if TYPE_CHECKING:
    from pkg.config import CloudSettings


class GoogleCloudStorage:
    """Thin, testable wrapper around Google Cloud Storage (inject `storage.Client` in tests)."""

    def __init__(
        self,
        bucket_name: str,
        *,
        client: storage.Client | None = None,
    ) -> None:
        if not bucket_name:
            raise ValueError("bucket_name is required")
        self._bucket_name = bucket_name
        self._client = client or storage.Client()
        self._bucket = self._client.bucket(bucket_name)

    @classmethod
    def from_settings(cls, settings: CloudSettings) -> GoogleCloudStorage:
        if not settings.gcs_bucket:
            raise ValueError("GCS_BUCKET must be set to build GoogleCloudStorage")
        return cls(bucket_name=settings.gcs_bucket)

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def blob_path(self, object_name: str) -> str:
        return f"gs://{self._bucket_name}/{object_name.lstrip('/')}"

    def upload_bytes(
        self,
        object_name: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        blob = self._bucket.blob(object_name.lstrip("/"))
        blob.upload_from_string(data, content_type=content_type)
        return self.blob_path(object_name)

    def download_bytes(self, object_name: str) -> bytes:
        blob = self._bucket.blob(object_name.lstrip("/"))
        return blob.download_as_bytes()

    def exists(self, object_name: str) -> bool:
        blob = self._bucket.blob(object_name.lstrip("/"))
        return bool(blob.exists())

    def delete(self, object_name: str) -> None:
        blob = self._bucket.blob(object_name.lstrip("/"))
        blob.delete()


def normalize_stored_to_object_key(
    stored: str, images_bucket: str | None
) -> str:
    """
    Return the GCS object key for this post (``posts/<id>/...``).

    Accepts a stored object key, or a legacy public GCS URL for that bucket, so
    the API can migrate without rewriting Mongo documents.
    """
    s = (stored or "").strip()
    pfx = "https://storage.googleapis.com/"
    if s.startswith(pfx) and images_bucket:
        without_host = s[len(pfx) :]
        bkt = f"{images_bucket}/"
        if without_host.startswith(bkt):
            return without_host[len(bkt) :]
    return s


def api_absolute_url_for_object_key(public_base: str, object_key: str) -> str:
    """
    Public URL to fetch an image through this API (served from private GCS via GET ``/images/...``).
    """
    from urllib.parse import quote

    base = public_base.rstrip("/")
    key = (object_key or "").strip().lstrip("/")
    if not key:
        return f"{base}/images/"
    parts = [quote(part, safe="") for part in key.split("/") if part]
    return f"{base}/images/{'/'.join(parts)}"
