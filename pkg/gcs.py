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


def public_https_url_for_gcs_object(bucket: str, object_name: str) -> str:
    """
    Public URL for the object, suitable for ``<img src>`` (bucket must allow public read).

    ``object_name`` is the key path inside the bucket (e.g. ``posts/<id>/<file>.png``).
    """
    from urllib.parse import quote

    clean = object_name.lstrip("/")
    encoded_path = "/".join(quote(part, safe="") for part in clean.split("/") if part)
    return f"https://storage.googleapis.com/{quote(bucket, safe='')}/{encoded_path}"
