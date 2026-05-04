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

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from pkg import EbayUserToken, InMemoryEbayTokenRepository
from product_analyzer import ProductAnalyzer
from product_analyzer.schema import AnalyzeProductImageResponse, PriceEstimate
from server import app, app_state


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
    assert body_a.get("listings") == []
    assert body_b.get("listings") == []
    assert body_a.get("image_urls") == []
    assert body_b.get("image_urls") == []

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
    r = client.get(f"/posts/{id_a}")
    assert r.status_code == 200
    assert r.json()["name"] == alpha_n

    r = client.get("/posts", params={"name": f"  {beta_n} "})
    assert r.status_code == 200
    assert r.json()["id"] == id_b

    r = client.get(
        "/posts",
        params={"name": beta_n, "include_deleted": "false"},
    )
    assert r.status_code == 200

    # --- update second post ---
    r = client.put(f"/posts/{id_b}", json={"name": gamma_n})
    assert r.status_code == 200
    assert r.json()["name"] == gamma_n

    r = client.get("/posts", params={"name": gamma_n})
    assert r.status_code == 200
    assert r.json()["id"] == id_b

    r = client.get("/posts", params={"name": beta_n})
    assert r.status_code == 404

    # --- soft delete first post ---
    r = client.delete(f"/posts/{id_a}")
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

    r = client.get(f"/posts/{id_a}")
    assert r.status_code == 404

    r = client.get(
        f"/posts/{id_a}",
        params={"include_deleted": "true"},
    )
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


def _assert_live_server_healthy(base: str) -> None:
    try:
        r = httpx.get(f"{base}/health", timeout=3.0)
    except httpx.ConnectError:
        pytest.skip(f"No server at {base} (start the app on localhost:8000)")
    if r.status_code != 200:
        pytest.skip(f"Server at {base} unhealthy: GET /health -> {r.status_code}")


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
    _assert_live_server_healthy(base)

    suffix = uuid.uuid4().hex[:12]
    with httpx.Client(base_url=base, timeout=30.0) as client:
        _run_full_post_crud_over_http(client, name_suffix=suffix, isolate=False)


@pytest.mark.e2e
@pytest.mark.live
def test_e2e_live_server_upload_airpods_prefills_required_ebay_fields() -> None:
    """Upload the AirPods fixture to localhost:8000 and verify draft fields are auto-prefilled."""
    base = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    _assert_live_server_healthy(base)

    image_path = Path("fixtures/airpods.jpg")
    if not image_path.exists():
        pytest.fail(f"missing test fixture: {image_path}")

    suffix = uuid.uuid4().hex[:10]
    description = f"Wireless earbuds with charging case {suffix}"
    user_id = f"live-e2e-{suffix}"

    with httpx.Client(base_url=base, timeout=90.0) as client:
        response = client.post(
            "/posts",
            data={"description": description, "user_id": user_id},
            files=[("files", (image_path.name, image_path.read_bytes(), "image/jpeg"))],
        )
        assert response.status_code == 201, response.text
        created = response.json()

        assert created["description"] == description
        assert created["analysis"] is not None
        assert str(created["analysis"].get("product_name") or "").strip()
        assert str(created["analysis"].get("brand") or "").strip()
        assert str(created["analysis"].get("model") or "").strip()
        assert str((created["analysis"].get("price_estimate") or {}).get("currency") or "").strip()

        draft = created["ebay_draft"]
        assert draft is not None
        assert draft["user_id"] == user_id
        assert str(draft.get("category_id") or "").strip()
        assert str(draft.get("title") or "").strip()
        assert str(draft.get("description") or "").strip()
        assert str(draft.get("condition") or "").strip()
        assert float(draft["price"]) > 0
        assert str(draft.get("currency") or "").strip()

        item_specifics = draft.get("item_specifics") or {}
        assert item_specifics.get("Brand", [""])[0].strip()
        assert item_specifics.get("Model", [""])[0].strip()

        # The description intentionally omits product-specific values like
        # color/connectivity, so any blank placeholder here means the
        # LLM-backed required-field prefill path did not complete its job.
        blank_required_fields = {
            key: values
            for key, values in item_specifics.items()
            if not (
                isinstance(values, list)
                and values
                and str(values[0]).strip()
            )
        }
        assert not blank_required_fields, item_specifics

        fetched = client.get(f"/posts/{created['id']}")
        assert fetched.status_code == 200, fetched.text
        persisted = fetched.json()
        assert persisted["analysis"] == created["analysis"]
        assert persisted["ebay_draft"] == created["ebay_draft"]

        delete_r = client.delete(f"/posts/{created['id']}")
        assert delete_r.status_code == 200, delete_r.text


# ---------------------------------------------------------------------------
# eBay listing creation E2E
# ---------------------------------------------------------------------------

_MINIMAL_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 12  # just enough for MIME detection


class _FakeEbayClient:
    """Stub that records calls and returns plausible success responses."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._sandbox = False

    def get_category_suggestions(self, query: str, *, marketplace_id: str | None = None):
        self.calls.append(("get_category_suggestions", query))
        return [SimpleNamespace(category_id="9355")]

    def get_valid_conditions(self, category_id: str, *, marketplace_id: str | None = None):
        self.calls.append(("get_valid_conditions", category_id))
        return ["NEW", "USED_EXCELLENT", "USED_GOOD"]

    def get_item_aspects_for_category(self, category_id: str, *, category_tree_id: str | None = None):
        self.calls.append(("get_item_aspects_for_category", category_id))
        return []

    def get_fulfillment_policies(self, user_token: str, *, marketplace_id: str | None = None):
        self.calls.append(("get_fulfillment_policies",))
        return [SimpleNamespace(policy_id="fulfill-1")]

    def get_payment_policies(self, user_token: str, *, marketplace_id: str | None = None):
        self.calls.append(("get_payment_policies",))
        return [SimpleNamespace(policy_id="payment-1")]

    def get_return_policies(self, user_token: str, *, marketplace_id: str | None = None):
        self.calls.append(("get_return_policies",))
        return [SimpleNamespace(policy_id="return-1")]

    def create_inventory_location(self, key: str, user_token: str, payload: dict):
        self.calls.append(("create_inventory_location",))

    def create_or_replace_inventory_item(self, sku: str, user_token: str, payload: dict):
        self.calls.append(("create_or_replace_inventory_item", sku, payload))

    def create_offer(self, user_token: str, payload: dict) -> str:
        self.calls.append(("create_offer", payload))
        return "offer-456"

    def publish_offer(self, offer_id: str, user_token: str) -> dict:
        self.calls.append(("publish_offer", offer_id))
        return {"listingId": "listing-456", "listingWebUrl": "https://www.ebay.com/itm/listing-456"}

    def get_offer(self, offer_id: str, user_token: str) -> dict:
        self.calls.append(("get_offer", offer_id))
        return {"offerId": offer_id, "listingId": "listing-456", "status": "PUBLISHED"}

    def update_offer(self, offer_id: str, user_token: str, payload: dict) -> dict:
        self.calls.append(("update_offer", offer_id, payload))
        return {}


def _seed_token(user_id: str) -> InMemoryEbayTokenRepository:
    repo = InMemoryEbayTokenRepository()
    repo.upsert(
        EbayUserToken(
            user_id=user_id,
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    return repo


def _fake_gemini_for(analysis: AnalyzeProductImageResponse):
    def _call(image_bytes: bytes, mime_type: str) -> tuple[str, dict[str, float]]:
        return json.dumps(analysis.model_dump(mode="json")), {"prompt_tokens": 5.0, "response_tokens": 5.0}

    return _call


@pytest.mark.e2e
def test_e2e_post_create_user_123_publishes_ebay_listing(e2e_client: TestClient) -> None:
    """POST /posts with user_id=123 builds an eBay draft; POST /ebay/publish creates the listing."""
    analysis = AnalyzeProductImageResponse(
        product_name="Apple AirPods Pro",
        brand="Apple",
        model="AirPods Pro",
        category="Earbud Headphones",
        condition_estimate="good",
        price_estimate=PriceEstimate(low=110, high=160, currency="USD", reasoning="r"),
    )
    fake_ebay = _FakeEbayClient()
    storage = MagicMock()
    storage.bucket_name = "mlops-images"
    storage.upload_bytes = MagicMock()

    app_state["product_analyzer"] = ProductAnalyzer(gemini_caller=_fake_gemini_for(analysis))
    app_state["images_storage"] = storage
    app_state["ebay_token_repository"] = _seed_token("123")
    try:
        with patch("server._get_ebay_client", lambda _: fake_ebay):
            # Step 1: create post — should build draft, not publish
            response = e2e_client.post(
                "/posts",
                data={"description": "AirPods Pro in great condition", "user_id": "123"},
                files=[("files", ("airpods.jpg", _MINIMAL_JPEG, "image/jpeg"))],
            )
            assert response.status_code == 201, response.text
            body = response.json()

            # Analysis was attached
            assert body["analysis"]["product_name"] == "Apple AirPods Pro"
            assert body["analysis"]["brand"] == "Apple"

            # Draft was built — no published eBay listing yet (only synthetic draft listings)
            assert not any("ebay.com" in (lst.get("marketplace_url") or "") for lst in body["listings"])
            assert body["ebay_draft"] is not None
            draft = body["ebay_draft"]
            assert draft["user_id"] == "123"
            assert draft["category_id"] == "9355"
            assert "title" in draft

            # Draft is persisted
            get_r = e2e_client.get(f"/posts/{body['id']}")
            assert get_r.status_code == 200, get_r.text
            assert get_r.json()["ebay_draft"] is not None

            # Draft creation call sequence
            draft_calls = [c[0] for c in fake_ebay.calls]
            assert draft_calls == [
                "get_category_suggestions",
                "get_valid_conditions",
                "get_item_aspects_for_category",
            ]
            assert fake_ebay.calls[0][1] == "Apple AirPods Pro"

            # Step 2: publish the draft
            fake_ebay.calls.clear()
            pub_r = e2e_client.post(f"/posts/{body['id']}/ebay/publish")
            assert pub_r.status_code == 200, pub_r.text
            pub_body = pub_r.json()

            # Listing was created
            assert len(pub_body["listings"]) == 1
            listing = pub_body["listings"][0]
            assert listing["id"] == "listing-456"
            assert listing["marketplace_url"] == "https://www.ebay.com/itm/listing-456"
            assert listing["status"] == "PUBLISHED"

            # Draft was cleared after successful publish
            assert pub_body["ebay_draft"] is None

            # Publish call sequence
            pub_call_names = [c[0] for c in fake_ebay.calls]
            assert pub_call_names == [
                "get_valid_conditions",
                "get_fulfillment_policies",
                "get_payment_policies",
                "get_return_policies",
                "create_inventory_location",
                "create_or_replace_inventory_item",
                "create_offer",
                "publish_offer",
                "get_offer",
                "update_offer",
            ]

            # Offer was created with the right category and SKU from the draft
            offer_payload = next(c[1] for c in fake_ebay.calls if c[0] == "create_offer")
            assert offer_payload["categoryId"] == "9355"
            assert offer_payload["sku"] == f"post-{body['id']}"

            # update_offer back-links the post; the description contains the post URL
            update_call = next(c for c in fake_ebay.calls if c[0] == "update_offer")
            assert update_call[1] == "offer-456"
            update_desc = update_call[2]["listingDescription"]
            assert f"/posts/{body['id']}" in update_desc
            assert update_desc.startswith(listing["description"])
    finally:
        app_state.pop("product_analyzer", None)
        app_state["images_storage"] = None
