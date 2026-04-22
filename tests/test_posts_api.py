"""HTTP tests for post CRUD (uses in-memory repository when MONGODB_URI is unset)."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server import app


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
    assert body["deleted_at"] is None

    r = client.get("/posts")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.post("/posts/get", json={"id": pid})
    assert r.status_code == 200
    assert r.json()["name"] == "hello"

    r = client.post("/posts/get", json={"name": "hello"})
    assert r.status_code == 200

    r = client.patch("/posts", json={"id": pid, "name": "bye"})
    assert r.status_code == 200
    assert r.json()["name"] == "bye"

    r = client.post("/posts/delete", json={"id": pid})
    assert r.status_code == 200
    assert r.json()["deleted_at"] is not None

    r = client.post("/posts/get", json={"id": pid})
    assert r.status_code == 404

    r = client.post("/posts/get", json={"id": pid, "include_deleted": True})
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
    r = client.post("/posts/get", json={"id": str(uuid.uuid4())})
    assert r.status_code == 404


def test_http_get_invalid_body_unprocessable(client: TestClient) -> None:
    r = client.post("/posts/get", json={})
    assert r.status_code == 422


def test_http_update_not_found(client: TestClient) -> None:
    r = client.patch("/posts", json={"id": str(uuid.uuid4()), "name": "n"})
    assert r.status_code == 404


def test_http_delete_not_found(client: TestClient) -> None:
    r = client.post("/posts/delete", json={"id": str(uuid.uuid4())})
    assert r.status_code == 404


@pytest.mark.integration
def test_http_posts_crud_with_mongo(mongo_container) -> None:
    uri = mongo_container.get_connection_url()
    db = f"http_posts_{uuid.uuid4().hex}"
    with patch.dict(os.environ, {"MONGODB_URI": uri, "MONGO_DATABASE": db}, clear=False):
        with TestClient(app) as client:
            r = client.post("/posts", json={"name": "mongo-post"})
            assert r.status_code == 201
            pid = r.json()["id"]
            r = client.get("/posts")
            assert len(r.json()) == 1
            r = client.post("/posts/delete", json={"id": pid})
            assert r.status_code == 200
            r = client.post("/posts", json={"name": "mongo-post"})
            assert r.status_code == 201
