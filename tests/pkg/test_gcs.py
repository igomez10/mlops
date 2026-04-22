from unittest.mock import MagicMock, patch

import pytest

from pkg.config import CloudSettings
from pkg.gcs import (
    GoogleCloudStorage,
    api_absolute_url_for_object_key,
    normalize_stored_to_object_key,
)


def test_google_cloud_storage_requires_bucket_name():
    with pytest.raises(ValueError, match="bucket_name"):
        GoogleCloudStorage("")


def test_google_cloud_storage_from_settings_requires_env_bucket(monkeypatch):
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    with pytest.raises(ValueError, match="GCS_BUCKET"):
        GoogleCloudStorage.from_settings(CloudSettings.from_env())


def test_upload_download_exists_delete_round_trip():
    bucket = MagicMock()
    blob = MagicMock()
    bucket.blob.return_value = blob

    client = MagicMock()
    client.bucket.return_value = bucket

    gcs = GoogleCloudStorage("my-bucket", client=client)

    assert gcs.bucket_name == "my-bucket"
    assert gcs.blob_path("a/b.txt") == "gs://my-bucket/a/b.txt"

    uri = gcs.upload_bytes("/a/b.txt", b"hello", content_type="text/plain")
    assert uri == "gs://my-bucket/a/b.txt"
    bucket.blob.assert_called_with("a/b.txt")
    blob.upload_from_string.assert_called_once_with(b"hello", content_type="text/plain")

    blob.download_as_bytes.return_value = b"world"
    assert gcs.download_bytes("a/b.txt") == b"world"

    blob.exists.return_value = True
    assert gcs.exists("a/b.txt") is True

    gcs.delete("a/b.txt")
    blob.delete.assert_called_once()


@patch("pkg.gcs.storage.Client")
def test_google_cloud_storage_default_client(mock_client_cls):
    bucket = MagicMock()
    mock_client = MagicMock()
    mock_client.bucket.return_value = bucket
    mock_client_cls.return_value = mock_client

    gcs = GoogleCloudStorage("bkt")
    mock_client_cls.assert_called_once()
    mock_client.bucket.assert_called_once_with("bkt")
    gcs.upload_bytes("x", b"1")
    bucket.blob.return_value.upload_from_string.assert_called()


def test_normalize_stored_to_object_key_strips_public_gcs_url():
    b = "my-bkt"
    key = "posts/abc-uuid/file.png"
    public = f"https://storage.googleapis.com/{b}/{key}"
    assert normalize_stored_to_object_key(public, b) == key
    assert normalize_stored_to_object_key(key, b) == key
    assert normalize_stored_to_object_key(key, None) == key


def test_api_absolute_url_for_object_key():
    assert (
        api_absolute_url_for_object_key(
            "https://api.example.com/",
            "posts/x/a b.png",
        )
        == "https://api.example.com/images/posts/x/a%20b.png"
    )
