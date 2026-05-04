from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from pkg import InMemoryEbayTokenRepository
from pkg.config import CloudSettings
from pkg.ebay import SELL_ACCOUNT_SCOPE, SELL_INVENTORY_SCOPE
from server import (
    CreatePostsRequest,
    _make_ebay_state,
    _parse_ebay_state,
    _pick_condition,
    _resolve_ebay_category_id,
    _resolve_posts_backend,
    app,
    app_state,
)


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
    # When the built UI is present (static/index.html), root serves HTML;
    # otherwise it returns the JSON welcome message.
    if response.headers.get("content-type", "").startswith("text/html"):
        assert b"<html" in response.content
    else:
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
        vertex_location="us-central1",
        mongodb_uri=None,
        posts_backend="auto",
    )
    assert _resolve_posts_backend(settings) == "firestore"


def test_ebay_authorize_returns_consent_url(monkeypatch):
    monkeypatch.setenv("EBAY_RUNAME", "test-runame")
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    monkeypatch.setenv("EBAY_CERT_ID", "test-cert-id")
    with TestClient(app) as test_client:
        response = test_client.get("/auth/ebay/authorize", params={"user_id": "user-123"})

        assert response.status_code == 200
        body = response.json()
        assert body["state"]
        assert SELL_INVENTORY_SCOPE in body["scopes"]
        assert SELL_ACCOUNT_SCOPE in body["scopes"]

        parsed = urlparse(body["authorization_url"])
        query = parse_qs(parsed.query)
        assert query["redirect_uri"] == ["test-runame"]
        assert query["state"] == [body["state"]]


def test_ebay_callback_stores_tokens(monkeypatch):
    class _FakeEbayClient:
        def exchange_authorization_code(self, code: str, *, runame: str) -> dict:
            assert code == "auth-code-123"
            assert runame == "test-runame"
            return {
                "access_token": "user-access",
                "refresh_token": "user-refresh",
                "expires_in": 7200,
                "refresh_token_expires_in": 47304000,
                "scope": f"{SELL_INVENTORY_SCOPE} {SELL_ACCOUNT_SCOPE}",
                "token_type": "User Access Token",
            }

    monkeypatch.setenv("EBAY_RUNAME", "test-runame")
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    monkeypatch.setenv("EBAY_CERT_ID", "test-cert-id")
    monkeypatch.setattr("server._get_ebay_client", lambda settings: _FakeEbayClient())
    with TestClient(app) as test_client:
        settings = app_state["cloud_settings"]
        repo = InMemoryEbayTokenRepository()
        app_state["ebay_token_repository"] = repo
        state = _make_ebay_state("user-123", settings)
        response = test_client.get(
            "/auth/ebay/callback",
            params={"code": "auth-code-123", "state": state},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == "user-123"
        assert body["refresh_token_present"] is True
        assert SELL_INVENTORY_SCOPE in body["scopes"]
        stored = repo.get_by_user_id("user-123")
        assert stored is not None
        assert stored.access_token == "user-access"
        assert stored.refresh_token == "user-refresh"


def test_ebay_callback_rejects_invalid_state(monkeypatch):
    monkeypatch.setenv("EBAY_RUNAME", "test-runame")
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    monkeypatch.setenv("EBAY_CERT_ID", "test-cert-id")
    with TestClient(app) as test_client:
        response = test_client.get(
            "/auth/ebay/callback",
            params={"code": "auth-code-123", "state": "bad-state"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid ebay state"


def test_ebay_state_round_trips_user_ids_with_colons(monkeypatch):
    monkeypatch.setenv("EBAY_RUNAME", "test-runame")
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    monkeypatch.setenv("EBAY_CERT_ID", "test-cert-id")
    with TestClient(app):
        settings = app_state["cloud_settings"]
        state = _make_ebay_state("user:segment:123", settings)

        assert isinstance(state, str)
        assert state.count(".") == 1
        assert _parse_ebay_state(state, settings) == "user:segment:123"


def test_ebay_listings_returns_aggregated_offers(monkeypatch):
    class _FakeEbayClient:
        def get_inventory_items(self, access_token: str, *, limit: int = 200, offset: int = 0):
            assert access_token == "user-access"
            assert limit == 200
            assert offset == 0
            return ["sku-1", "sku-2"], None

        def get_offers(self, access_token: str, *, sku: str):
            assert access_token == "user-access"
            if sku == "sku-1":
                return [
                    type(
                        "Offer",
                        (),
                        {
                            "sku": "sku-1",
                            "offer_id": "offer-1",
                            "listing_id": "listing-1",
                            "marketplace_id": "EBAY_US",
                            "format": "FIXED_PRICE",
                            "available_quantity": 2,
                            "category_id": "9355",
                            "merchant_location_key": "loc-1",
                            "listing_description": "First listing",
                            "status": "PUBLISHED",
                            "price": 19.99,
                            "currency": "USD",
                        },
                    )()
                ]
            return []

    monkeypatch.setattr("server._get_ebay_client", lambda settings: _FakeEbayClient())
    with TestClient(app) as test_client:
        repo = InMemoryEbayTokenRepository()
        now = datetime.now(timezone.utc)
        repo.upsert(
            type(
                "Token",
                (),
                {
                    "user_id": "123",
                    "access_token": "user-access",
                    "refresh_token": "user-refresh",
                    "token_type": "Bearer",
                    "scopes": [SELL_INVENTORY_SCOPE, SELL_ACCOUNT_SCOPE],
                    "expires_at": now + timedelta(hours=1),
                    "refresh_token_expires_at": None,
                    "created_at": now,
                    "updated_at": now,
                },
            )()
        )
        app_state["ebay_token_repository"] = repo

        response = test_client.get("/ebay/listings", params={"user": "123"})

        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == "123"
        assert body["listings"] == [
            {
                "sku": "sku-1",
                "offer_id": "offer-1",
                "listing_id": "listing-1",
                "marketplace_id": "EBAY_US",
                "format": "FIXED_PRICE",
                "available_quantity": 2,
                "category_id": "9355",
                "merchant_location_key": "loc-1",
                "listing_description": "First listing",
                "status": "PUBLISHED",
                "price": 19.99,
                "currency": "USD",
            }
        ]


def test_ebay_listings_refreshes_expired_token(monkeypatch):
    class _FakeEbayClient:
        def refresh_user_access_token(self, refresh_token: str, *, scopes=None) -> dict:
            assert refresh_token == "refresh-123"
            return {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 7200,
                "scope": f"{SELL_INVENTORY_SCOPE} {SELL_ACCOUNT_SCOPE}",
                "token_type": "User Access Token",
            }

        def get_inventory_items(self, access_token: str, *, limit: int = 200, offset: int = 0):
            assert access_token == "new-access"
            return [], None

        def get_offers(self, access_token: str, *, sku: str):
            raise AssertionError("should not fetch offers when there are no SKUs")

    monkeypatch.setattr("server._get_ebay_client", lambda settings: _FakeEbayClient())
    with TestClient(app) as test_client:
        repo = InMemoryEbayTokenRepository()
        now = datetime.now(timezone.utc)
        repo.upsert(
            type(
                "Token",
                (),
                {
                    "user_id": "123",
                    "access_token": "old-access",
                    "refresh_token": "refresh-123",
                    "token_type": "Bearer",
                    "scopes": [SELL_INVENTORY_SCOPE, SELL_ACCOUNT_SCOPE],
                    "expires_at": now - timedelta(minutes=1),
                    "refresh_token_expires_at": None,
                    "created_at": now - timedelta(days=1),
                    "updated_at": now - timedelta(days=1),
                },
            )()
        )
        app_state["ebay_token_repository"] = repo

        response = test_client.get("/ebay/listings", params={"user": "123"})

        assert response.status_code == 200
        stored = repo.get_by_user_id("123")
        assert stored is not None
        assert stored.access_token == "new-access"
        assert stored.refresh_token == "new-refresh"


def test_ebay_listings_returns_404_without_token():
    with TestClient(app) as test_client:
        app_state["ebay_token_repository"] = InMemoryEbayTokenRepository()

        response = test_client.get("/ebay/listings", params={"user": "missing"})

        assert response.status_code == 404
        assert response.json()["detail"] == "ebay token not found"


def test_ebay_accepted_page_shows_simple_message(monkeypatch):
    class _FakeEbayClient:
        def exchange_authorization_code(self, code: str, *, runame: str) -> dict:
            return {
                "access_token": "user-access",
                "refresh_token": "user-refresh",
                "expires_in": 7200,
                "refresh_token_expires_in": 47304000,
                "scope": f"{SELL_INVENTORY_SCOPE} {SELL_ACCOUNT_SCOPE}",
                "token_type": "User Access Token",
            }

    monkeypatch.setenv("EBAY_RUNAME", "test-runame")
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    monkeypatch.setenv("EBAY_CERT_ID", "test-cert-id")
    monkeypatch.setattr("server._get_ebay_client", lambda settings: _FakeEbayClient())
    with TestClient(app) as test_client:
        settings = app_state["cloud_settings"]
        app_state["ebay_token_repository"] = InMemoryEbayTokenRepository()
        state = _make_ebay_state("user-123", settings)
        response = test_client.get(
            "/auth/ebay/accepted",
            params={"code": "auth-code-123", "state": state},
        )

        assert response.status_code == 200
        assert "eBay authorization accepted" in response.text
        assert "close this window" in response.text


def test_ebay_rejected_page_shows_simple_message(client):
    response = client.get(
        "/auth/ebay/rejected",
        params={"error": "access_denied", "error_description": "User declined access"},
    )

    assert response.status_code == 200
    assert "eBay authorization rejected" in response.text
    assert "User declined access" in response.text


def test_ebay_rejected_page_escapes_message(client):
    response = client.get(
        "/auth/ebay/rejected",
        params={"error_description": "<script>alert(1)</script>"},
    )

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


# ---------------------------------------------------------------------------
# _resolve_ebay_category_id
# ---------------------------------------------------------------------------


def _make_category_client(query_assert: str | None, category_id: str):
    class _Client:
        def get_category_suggestions(self, query, *, marketplace_id=None):
            if query_assert is not None:
                assert query == query_assert, f"expected query {query_assert!r}, got {query!r}"
            return [SimpleNamespace(category_id=category_id)]

    return _Client()


def test_resolve_ebay_category_id_uses_product_name():
    category_id = _resolve_ebay_category_id(
        {"product_name": "Apple AirPods Pro"},
        "fallback description",
        client=_make_category_client("Apple AirPods Pro", "9355"),
        marketplace_id="EBAY_US",
    )
    assert category_id == "9355"


def test_resolve_ebay_category_id_falls_back_to_description_when_product_name_absent():
    category_id = _resolve_ebay_category_id(
        {},
        "used headphones",
        client=_make_category_client("used headphones", "112529"),
        marketplace_id="EBAY_US",
    )
    assert category_id == "112529"


def test_resolve_ebay_category_id_falls_back_when_product_name_is_blank():
    category_id = _resolve_ebay_category_id(
        {"product_name": "   "},
        "bicycle frame",
        client=_make_category_client("bicycle frame", "7294"),
        marketplace_id="EBAY_US",
    )
    assert category_id == "7294"


def test_resolve_ebay_category_id_returns_first_suggestion():
    class _Client:
        def get_category_suggestions(self, query, *, marketplace_id=None):
            return [
                SimpleNamespace(category_id="first-cat"),
                SimpleNamespace(category_id="second-cat"),
                SimpleNamespace(category_id="third-cat"),
            ]

    category_id = _resolve_ebay_category_id(
        {"product_name": "some product"},
        "fallback",
        client=_Client(),
        marketplace_id="EBAY_US",
    )
    assert category_id == "first-cat"


def test_resolve_ebay_category_id_raises_when_no_suggestions():
    class _Client:
        def get_category_suggestions(self, query, *, marketplace_id=None):
            return []

    with pytest.raises(RuntimeError, match="no eBay category suggestions"):
        _resolve_ebay_category_id(
            {"product_name": "rare item"},
            "fallback",
            client=_Client(),
            marketplace_id="EBAY_US",
        )


# ---------------------------------------------------------------------------
# _pick_condition
# ---------------------------------------------------------------------------


def test_pick_condition_returns_desired_when_valid():
    assert _pick_condition("USED_GOOD", ["NEW", "USED_GOOD", "USED_EXCELLENT"]) == "USED_GOOD"


def test_pick_condition_upgrades_when_desired_not_available():
    # USED_GOOD not available — should upgrade to USED_EXCELLENT
    assert _pick_condition("USED_GOOD", ["NEW", "USED_EXCELLENT"]) == "USED_EXCELLENT"


def test_pick_condition_upgrades_to_new_as_last_resort():
    assert _pick_condition("USED_ACCEPTABLE", ["NEW"]) == "NEW"


def test_pick_condition_downgrades_when_no_better_option():
    # Only a worse condition is available
    assert _pick_condition("USED_EXCELLENT", ["USED_GOOD"]) == "USED_GOOD"


def test_pick_condition_returns_first_valid_for_unknown_desired():
    assert _pick_condition("SOME_UNKNOWN", ["USED_GOOD", "NEW"]) == "USED_GOOD"


def test_pick_condition_returns_desired_when_no_valid_list():
    assert _pick_condition("USED_GOOD", []) == "USED_GOOD"
