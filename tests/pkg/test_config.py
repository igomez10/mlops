import os

from pkg.config import CloudSettings


def test_cloud_settings_from_env_defaults(monkeypatch):
    for key in (
        "GOOGLE_CLOUD_PROJECT",
        "GCP_PROJECT",
        "GCLOUD_PROJECT",
        "GCS_BUCKET",
        "FIRESTORE_DATABASE_ID",
        "GEMINI_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_USE_VERTEX",
        "GOOGLE_CLOUD_LOCATION",
        "MONGODB_URI",
    ):
        monkeypatch.delenv(key, raising=False)

    s = CloudSettings.from_env()
    assert s.gcp_project_id is None
    assert s.gcs_bucket is None
    assert s.firestore_database_id == "(default)"
    assert s.gemini_model == "gemini-2.0-flash"
    assert s.gemini_api_key is None
    assert s.gemini_use_vertex is False
    assert s.vertex_location == "us-central1"
    assert s.mongodb_uri is None
    assert s.posts_backend == "auto"


def test_cloud_settings_from_env_overrides(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    monkeypatch.setenv("GCS_BUCKET", "bucket-1")
    monkeypatch.setenv("FIRESTORE_DATABASE_ID", "db-1")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_API_KEY", "key-1")
    monkeypatch.setenv("GEMINI_USE_VERTEX", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
    monkeypatch.setenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    monkeypatch.setenv("POSTS_BACKEND", "firestore")

    s = CloudSettings.from_env()
    assert s.gcp_project_id == "proj-1"
    assert s.gcs_bucket == "bucket-1"
    assert s.firestore_database_id == "db-1"
    assert s.gemini_model == "gemini-test"
    assert s.gemini_api_key == "key-1"
    assert s.gemini_use_vertex is True
    assert s.vertex_location == "europe-west1"
    assert s.mongodb_uri == "mongodb://127.0.0.1:27017"
    assert s.posts_backend == "firestore"


def test_cloud_settings_prefers_google_cloud_project(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "a")
    monkeypatch.setenv("GCP_PROJECT", "b")
    assert CloudSettings.from_env().gcp_project_id == os.environ["GOOGLE_CLOUD_PROJECT"]
