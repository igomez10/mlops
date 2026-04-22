"""HTTP tests for post CRUD (uses in-memory repository when MONGODB_URI is unset)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from server import app, app_state


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_http_create_list_get_update_soft_delete_flow(client: TestClient) -> None:
    r = client.post("/posts", json={"name": "hello"})
    assert r.status_code == 201
    body = r.json()
    pid = body["id"]
    assert body["name"] == "hello"
    assert body.get("description") == ""
    assert body["deleted_at"] is None
    assert body["listings"] == []
    assert body["image_urls"] == []

    r = client.get("/posts")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/posts/{pid}")
    assert r.status_code == 200
    assert r.json()["name"] == "hello"

    r = client.get("/posts", params={"name": "hello"})
    assert r.status_code == 200
    assert r.json()["name"] == "hello"

    r = client.put(f"/posts/{pid}", json={"name": "bye"})
    assert r.status_code == 200
    assert r.json()["name"] == "bye"

    r = client.delete(f"/posts/{pid}")
    assert r.status_code == 200
    assert r.json()["deleted_at"] is not None

    r = client.get(f"/posts/{pid}")
    assert r.status_code == 404

    r = client.get(
        f"/posts/{pid}",
        params={"include_deleted": "true"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "bye"

    r = client.get("/posts")
    assert r.status_code == 200
    assert r.json() == []

    r = client.get("/posts", params={"include_deleted": "true"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_http_create_duplicate_name_400(client: TestClient) -> None:
    assert client.post("/posts", json={"name": "x"}).status_code == 201
    r = client.post("/posts", json={"name": "x"})
    assert r.status_code == 400


def test_http_get_not_found(client: TestClient) -> None:
    missing = str(uuid.uuid4())
    r = client.get(f"/posts/{missing}")
    assert r.status_code == 404


def test_http_put_post_invalid_body_unprocessable(client: TestClient) -> None:
    r = client.post("/posts", json={"name": "p"})
    pid = r.json()["id"]
    r = client.put(f"/posts/{pid}", json={})
    assert r.status_code == 422


def test_http_create_post_with_images_synthetic_listings(
    client: TestClient,
) -> None:
    store = MagicMock()
    store.bucket_name = "mlops-images"
    store.upload_bytes = MagicMock()
    app_state["images_storage"] = store
    try:
        r = client.post(
            "/posts",
            data={"description": "My new listing photo"},
            files=[("files", ("a.png", b"\x89PNG\r\n\x1a\n\x00\x00", "image/png"))],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["description"] == "My new listing photo"
        assert body["name"].startswith("p-")
        assert len(body["image_urls"]) == 1
        assert body["image_urls"][0].startswith("http://testserver/images/posts/")
        assert len(body["listings"]) == 1
        assert body["listings"][0]["image_url"] == body["image_urls"][0]
        assert body["listings"][0]["status"] == "draft"
        store.upload_bytes.assert_called_once()
        # Stored value is the object key, not a public GCS URL
        pid = body["id"]
        assert store.upload_bytes.call_args[0][0].startswith(f"posts/{pid}/")
    finally:
        app_state["images_storage"] = None


def test_get_post_image_proxies_from_private_gcs(client: TestClient) -> None:
    store = MagicMock()
    store.bucket_name = "mlops-images"
    store.upload_bytes = MagicMock()
    store.exists = MagicMock(return_value=True)
    store.download_bytes = MagicMock(return_value=b"\x89PNG_PROXY")
    app_state["images_storage"] = store
    try:
        r = client.post(
            "/posts",
            data={"description": "photo"},
            files=[("files", ("a.png", b"\x89PNG\n", "image/png"))],
        )
        assert r.status_code == 201
        url = r.json()["image_urls"][0]
        r2 = client.get(urlparse(url).path)
        assert r2.status_code == 200
        assert r2.content == b"\x89PNG_PROXY"
        assert "image" in (r2.headers.get("content-type") or "")
        store.exists.assert_called()
        store.download_bytes.assert_called()
    finally:
        app_state["images_storage"] = None


def test_get_post_image_404_for_unknown_path(client: TestClient) -> None:
    store = MagicMock()
    store.bucket_name = "b"
    app_state["images_storage"] = store
    try:
        r = client.get(
            "/images/posts/00000000-0000-0000-0000-000000000000/nope.png",
        )
        assert r.status_code == 404
    finally:
        app_state["images_storage"] = None


def test_http_create_post_images_503_without_bucket(client: TestClient) -> None:
    app_state["images_storage"] = None
    r = client.post(
        "/posts",
        data={"description": "x"},
        files=[("files", ("a.png", b"x", "image/png"))],
    )
    assert r.status_code == 503


def test_http_update_not_found(client: TestClient) -> None:
    r = client.put(
        f"/posts/{str(uuid.uuid4())}",
        json={"name": "n"},
    )
    assert r.status_code == 404


def test_http_delete_not_found(client: TestClient) -> None:
    r = client.delete(f"/posts/{str(uuid.uuid4())}")
    assert r.status_code == 404


def test_create_posts_wrong_content_type_415(client: TestClient) -> None:
    r = client.post(
        "/posts",
        data="name=x",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 415


@pytest.mark.integration
def test_http_posts_crud_with_mongo(mongo_container) -> None:
    uri = mongo_container.get_connection_url()
    db = f"http_posts_{uuid.uuid4().hex}"
    with patch.dict(
        os.environ, {"MONGODB_URI": uri, "MONGO_DATABASE": db}, clear=False
    ):
        with TestClient(app) as client:
            r = client.post("/posts", json={"name": "mongo-post"})
            assert r.status_code == 201
            pid = r.json()["id"]
            r = client.get("/posts")
            assert len(r.json()) == 1
            r = client.delete(f"/posts/{pid}")
            assert r.status_code == 200
            r = client.post("/posts", json={"name": "mongo-post"})
            assert r.status_code == 201
