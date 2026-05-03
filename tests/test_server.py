import pytest
from fastapi.testclient import TestClient

from pkg.config import CloudSettings
from server import CreatePostsRequest, _resolve_posts_backend, app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to mlops fastapi!"}


def test_usfca(client):
    response = client.get("/usfca")
    assert response.status_code == 200
    assert response.json() == "something"


def test_add_query_parameters(client):
    response = client.post("/add_query_parameters?num1=3&num2=4")
    assert response.status_code == 200
    assert response.json() == {"result": 7}


def test_add_body_parameters(client):
    response = client.post("/add_body_parameters", json={"num1": 1, "num2": 2})
    assert response.status_code == 200
    b0, b1, b2 = 27, 256, 339
    assert response.json() == {"result": b0 + b1 * 1 + b2 * 2}


def test_predict(client):
    response = client.post("/predict_price_sqft", json={"sqft": 1500, "rooms": 3})
    assert response.status_code == 200
    assert response.json() == {"prediction": 450000}


def test_create_valid_post_request():
    valid_request = CreatePostsRequest(
        dry_run=True,
        platform="ebay",
        user_estimated_price=50000,
        images=[b"123"],
        user_id=123,
    )

    assert valid_request.validate_request() is True


def test_create_post_invalid_platform():
    request = CreatePostsRequest(
        dry_run=False,
        platform="amazon",
        user_estimated_price=10000,
        images=[b"abc"],
        user_id=1,
    )
    with pytest.raises(ValueError, match="Invalid platform: amazon"):
        request.validate_request()


def test_create_invalid_post_request():
    invalid_request = CreatePostsRequest(
        dry_run=True,
        platform="ebay",
        user_estimated_price=50000,
        images=[b"123"],
        user_id=123,
    )

    # Missing required field 'platform'
    invalid_request.platform = None
    with pytest.raises(ValueError, match="Missing required field: platform"):
        invalid_request.validate_request()

    # Invalid platform value
    invalid_request.platform = "invalid_platform"
    with pytest.raises(ValueError, match="Invalid platform: invalid_platform"):
        invalid_request.validate_request()


def test_resolve_posts_backend_prefers_mongodb_when_uri_present(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    settings = CloudSettings(
        gcp_project_id=None,
        gcs_bucket=None,
        gcs_images_bucket=None,
        firestore_database_id="(default)",
        gemini_model="gemini-2.0-flash",
        gemini_api_key=None,
        gemini_use_vertex=False,
        vertex_location="us-central1",
        mongodb_uri="mongodb://127.0.0.1:27017",
        posts_backend="auto",
    )
    assert _resolve_posts_backend(settings) == "mongodb"


def test_resolve_posts_backend_uses_firestore_on_cloud_run(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "fastapi")
    settings = CloudSettings(
        gcp_project_id="proj-1",
        gcs_bucket=None,
        gcs_images_bucket=None,
        firestore_database_id="(default)",
        gemini_model="gemini-2.0-flash",
        gemini_api_key=None,
        gemini_use_vertex=False,
        vertex_location="us-central1",
        mongodb_uri=None,
        posts_backend="auto",
    )
    assert _resolve_posts_backend(settings) == "firestore"
