"""End-to-end tests: drive all post CRUD routes over HTTP.

- **In-process:** :class:`fastapi.testclient.TestClient` (default E2E tests).
- **Live server:** ``httpx`` against ``E2E_BASE_URL`` (default ``http://127.0.0.1:8000``);
  skipped if nothing is listening. Uses unique post names so an existing Mongo DB does
  not break assertions.

Soft-deleted posts keep ``deleted_at`` set; use ``include_deleted`` on list/get to see them.

**Mongo testcontainers E2E:** database ``e2e_posts_<uuid>`` is left on the instance for inspection.

When running the real app against Compose, use ``MONGO_DATABASE`` (default ``mlops``) and collection ``posts``.
"""

from __future__ import annotations

import os
import uuid
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from server import app


def _post_names(name_suffix: str) -> tuple[str, str, str]:
    """Distinct names for the flow; first name is reused after soft-delete."""
    if not name_suffix:
        return "alpha", "beta", "gamma"
    s = name_suffix
    return f"alpha-{s}", f"beta-{s}", f"gamma-{s}"


def _our_posts(rows: list[dict], want_ids: set[str]) -> list[dict]:
    """Subset of list response for posts we created in this run, by ``created_at``."""
    return sorted(
        [r for r in rows if r["id"] in want_ids],
        key=lambda r: r["created_at"],
    )


def _run_full_post_crud_over_http(
    client: Any,
    *,
    name_suffix: str = "",
    isolate: bool = True,
) -> None:
    """Exercise create, read (by id/name + list), update, soft-delete, tombstone reads."""
    alpha_n, beta_n, gamma_n = _post_names(name_suffix)

    # --- list (optionally empty when isolated DB) ---
    r = client.get("/posts")
    assert r.status_code == 200
    initial = r.json()
    if isolate:
        assert initial == []

    # --- create two posts ---
    r = client.post("/posts", json={"name": alpha_n})
    assert r.status_code == 201
    body_a = r.json()
    id_a = body_a["id"]
    assert body_a["name"] == alpha_n
    assert body_a["deleted_at"] is None

    r = client.post("/posts", json={"name": beta_n})
    assert r.status_code == 201
    body_b = r.json()
    id_b = body_b["id"]
    assert body_b["name"] == beta_n
    assert id_b != id_a

    our_ids: set[str] = {id_a, id_b}

    # --- list our active posts (ordered by created_at among ours) ---
    r = client.get("/posts")
    assert r.status_code == 200
    rows = r.json()
    ours = _our_posts(rows, our_ids)
    assert len(ours) == 2
    assert [row["id"] for row in ours] == [id_a, id_b]
    assert [row["name"] for row in ours] == [alpha_n, beta_n]

    # --- read one by id and by name ---
    r = client.post("/posts/get", json={"id": id_a})
    assert r.status_code == 200
    assert r.json()["name"] == alpha_n

    r = client.post("/posts/get", json={"name": f"  {beta_n} "})
    assert r.status_code == 200
    assert r.json()["id"] == id_b

    r = client.post(
        "/posts/get",
        json={"name": beta_n, "include_deleted": False},
    )
    assert r.status_code == 200

    # --- update second post ---
    r = client.patch("/posts", json={"id": id_b, "name": gamma_n})
    assert r.status_code == 200
    assert r.json()["name"] == gamma_n

    r = client.post("/posts/get", json={"name": gamma_n})
    assert r.status_code == 200
    assert r.json()["id"] == id_b

    r = client.post("/posts/get", json={"name": beta_n})
    assert r.status_code == 404

    # --- soft delete first post ---
    r = client.post("/posts/delete", json={"id": id_a})
    assert r.status_code == 200
    del_body = r.json()
    assert del_body["id"] == id_a
    assert del_body["deleted_at"] is not None

    # --- our active list shrinks; default get by id returns 404 ---
    r = client.get("/posts")
    assert r.status_code == 200
    active = r.json()
    ours_active = _our_posts(active, our_ids)
    assert len(ours_active) == 1
    assert ours_active[0]["id"] == id_b
    assert ours_active[0]["name"] == gamma_n

    r = client.post("/posts/get", json={"id": id_a})
    assert r.status_code == 404

    r = client.post("/posts/get", json={"id": id_a, "include_deleted": True})
    assert r.status_code == 200
    assert r.json()["name"] == alpha_n

    r = client.get("/posts", params={"include_deleted": "true"})
    assert r.status_code == 200
    tomb = r.json()
    ours_tomb = _our_posts(tomb, our_ids)
    assert len(ours_tomb) == 2
    assert {row["id"] for row in ours_tomb} == {id_a, id_b}
    by_id = {row["id"]: row for row in ours_tomb}
    assert by_id[id_a]["deleted_at"] is not None, "soft-deleted row must carry deleted_at"
    assert by_id[id_b]["deleted_at"] is None

    # --- name freed after soft delete: create again ---
    r = client.post("/posts", json={"name": alpha_n})
    assert r.status_code == 201
    id_c = r.json()["id"]
    assert id_c not in (id_a, id_b)
    our_ids.add(id_c)

    r = client.get("/posts")
    assert r.status_code == 200
    assert len(_our_posts(r.json(), our_ids)) == 2

    r = client.get("/posts", params={"include_deleted": "true"})
    assert r.status_code == 200
    full = r.json()
    ours_full = _our_posts(full, our_ids)
    assert len(ours_full) == 3
    by_id_final = {row["id"]: row for row in ours_full}
    assert by_id_final[id_a]["deleted_at"] is not None
    assert by_id_final[id_b]["deleted_at"] is None
    assert by_id_final[id_c]["deleted_at"] is None


@pytest.fixture
def e2e_client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.e2e
def test_e2e_posts_crud_in_memory(e2e_client: TestClient) -> None:
    _run_full_post_crud_over_http(e2e_client, isolate=True)


@pytest.mark.e2e
@pytest.mark.integration
def test_e2e_posts_crud_with_mongo(mongo_container) -> None:
    uri = mongo_container.get_connection_url()
    db = f"e2e_posts_{uuid.uuid4().hex}"
    mongo_admin = MongoClient(uri)
    try:
        with patch.dict(os.environ, {"MONGODB_URI": uri, "MONGO_DATABASE": db}, clear=False):
            with TestClient(app) as client:
                _run_full_post_crud_over_http(client, isolate=True)
        posts_coll = mongo_admin[db]["posts"]
        docs = list(posts_coll.find({}))
        assert len(docs) == 3
        assert sum(1 for d in docs if d.get("deleted_at") is not None) == 1
    finally:
        mongo_admin.close()


@pytest.mark.e2e
@pytest.mark.live
def test_e2e_posts_crud_live_server() -> None:
    """Hit a real uvicorn process (e.g. ``make dev-server``). Skips if host is down."""
    base = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        r = httpx.get(f"{base}/health", timeout=3.0)
    except httpx.ConnectError:
        pytest.skip(f"No server at {base} (start the app, e.g. make dev-server)")
    if r.status_code != 200:
        pytest.skip(f"Server at {base} unhealthy: GET /health -> {r.status_code}")

    suffix = uuid.uuid4().hex[:12]
    with httpx.Client(base_url=base, timeout=30.0) as client:
        _run_full_post_crud_over_http(client, name_suffix=suffix, isolate=False)
