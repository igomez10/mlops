"""Unit tests for pkg.ebay — all network calls are intercepted via httpx.MockTransport."""
from __future__ import annotations

import base64
import time

import httpx
import pytest

from pkg.config import CloudSettings
from pkg.ebay import EbayClient, ItemSummary, SearchResult, _parse_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(**overrides) -> CloudSettings:
    base = dict(
        gcp_project_id=None,
        gcs_bucket=None,
        gcs_images_bucket=None,
        firestore_database_id="(default)",
        gemini_model="gemini-2.0-flash",
        gemini_api_key=None,
        gemini_use_vertex=False,
        vertex_location="us-central1",
        mongodb_uri=None,
        ebay_app_id="test-app-id",
        ebay_cert_id="test-cert-id",
        ebay_sandbox=False,
    )
    base.update(overrides)
    return CloudSettings(**base)


def _token_response(token: str = "tok-abc", expires_in: int = 7200) -> dict:
    return {"access_token": token, "expires_in": expires_in, "token_type": "Application Access Token"}


def _search_response(items: list[dict] | None = None, total: int | None = None) -> dict:
    items = items or []
    return {"total": total if total is not None else len(items), "itemSummaries": items}


def _item_summary_raw(
    item_id: str = "v1|123|0",
    title: str = "Test Item",
    price: str = "9.99",
    currency: str = "USD",
    condition: str = "New",
    item_url: str = "https://www.ebay.com/itm/123",
    image_url: str = "https://i.ebayimg.com/img.jpg",
) -> dict:
    return {
        "itemId": item_id,
        "title": title,
        "price": {"value": price, "currency": currency},
        "condition": condition,
        "itemWebUrl": item_url,
        "image": {"imageUrl": image_url},
    }


class _MockTransport(httpx.MockTransport):
    """Records requests and dispatches canned responses in order."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._responses = list(responses)
        self._index = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self._responses[self._index % len(self._responses)]
        self._index += 1
        return response


def _json_response(body: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=body)


def _make_client(responses: list[httpx.Response]) -> tuple[EbayClient, _MockTransport]:
    transport = _MockTransport(responses)
    http = httpx.Client(transport=transport)
    client = EbayClient("app-id", "cert-id", http_client=http)
    return client, transport


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

def test_requires_client_id():
    with pytest.raises(ValueError, match="client_id"):
        EbayClient("", "cert")


def test_requires_client_secret():
    with pytest.raises(ValueError, match="client_secret"):
        EbayClient("app", "")


# ---------------------------------------------------------------------------
# from_settings
# ---------------------------------------------------------------------------

def test_from_settings_creates_client():
    client = EbayClient.from_settings(_settings())
    assert client._client_id == "test-app-id"
    assert client._client_secret == "test-cert-id"


def test_sandbox_uses_sandbox_urls():
    transport = _MockTransport([
        _json_response(_token_response()),
        _json_response(_search_response()),
    ])
    http = httpx.Client(transport=transport)
    client = EbayClient("a", "b", sandbox=True, http_client=http)
    client.search_items("test")

    assert "sandbox.ebay.com" in str(transport.requests[0].url)
    assert "sandbox.ebay.com" in str(transport.requests[1].url)


def test_production_uses_production_urls():
    transport = _MockTransport([
        _json_response(_token_response()),
        _json_response(_search_response()),
    ])
    http = httpx.Client(transport=transport)
    client = EbayClient("a", "b", sandbox=False, http_client=http)
    client.search_items("test")

    assert "sandbox" not in str(transport.requests[0].url)
    assert "sandbox" not in str(transport.requests[1].url)


def test_from_settings_sandbox_flag():
    client = EbayClient.from_settings(_settings(ebay_sandbox=True))
    assert "sandbox" in client._token_url


def test_from_settings_missing_app_id():
    with pytest.raises(ValueError, match="EBAY_APP_ID"):
        EbayClient.from_settings(_settings(ebay_app_id=None))


def test_from_settings_missing_cert_id():
    with pytest.raises(ValueError, match="EBAY_CERT_ID"):
        EbayClient.from_settings(_settings(ebay_cert_id=None))


# ---------------------------------------------------------------------------
# OAuth token fetching
# ---------------------------------------------------------------------------

def test_token_request_uses_basic_auth():
    client, transport = _make_client([
        _json_response(_token_response()),
        _json_response(_search_response()),
    ])
    client.search_items("laptop")

    token_req = transport.requests[0]
    assert token_req.method == "POST"
    assert "identity/v1/oauth2/token" in str(token_req.url)

    expected = base64.b64encode(b"app-id:cert-id").decode()
    assert token_req.headers["Authorization"] == f"Basic {expected}"
    assert token_req.headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_token_is_cached_across_calls():
    client, transport = _make_client([
        _json_response(_token_response()),
        _json_response(_search_response()),
        _json_response(_search_response()),
    ])
    client.search_items("a")
    client.search_items("b")

    token_requests = [r for r in transport.requests if "oauth2/token" in str(r.url)]
    assert len(token_requests) == 1


def test_expired_token_is_refreshed(monkeypatch):
    client, transport = _make_client([
        _json_response(_token_response()),
        _json_response(_search_response()),
        _json_response(_token_response("tok-new")),
        _json_response(_search_response()),
    ])
    client.search_items("a")

    # Simulate token expiry
    client._token_cache.expires_at = time.monotonic() - 1

    client.search_items("b")

    token_requests = [r for r in transport.requests if "oauth2/token" in str(r.url)]
    assert len(token_requests) == 2


def test_token_forwarded_as_bearer_in_search():
    client, transport = _make_client([
        _json_response(_token_response("my-token")),
        _json_response(_search_response()),
    ])
    client.search_items("watch")

    search_req = transport.requests[1]
    assert search_req.headers["Authorization"] == "Bearer my-token"


# ---------------------------------------------------------------------------
# search_items
# ---------------------------------------------------------------------------

def test_search_items_url_and_params():
    client, transport = _make_client([
        _json_response(_token_response()),
        _json_response(_search_response()),
    ])
    client.search_items("iphone", limit=5, offset=10)

    req = transport.requests[1]
    assert "/item_summary/search" in str(req.url)
    assert "q=iphone" in str(req.url)
    assert "limit=5" in str(req.url)
    assert "offset=10" in str(req.url)


def test_search_items_with_filter():
    client, transport = _make_client([
        _json_response(_token_response()),
        _json_response(_search_response()),
    ])
    client.search_items("shoes", filter="price:[10..50]")

    req = transport.requests[1]
    assert "filter=" in str(req.url)


def test_search_items_marketplace_header():
    transport = _MockTransport([
        _json_response(_token_response()),
        _json_response(_search_response()),
    ])
    http = httpx.Client(transport=transport)
    client = EbayClient("a", "b", marketplace_id="EBAY_GB", http_client=http)
    client.search_items("tea")

    req = transport.requests[1]
    assert req.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"


def test_search_items_returns_result():
    raw = _item_summary_raw()
    client, _ = _make_client([
        _json_response(_token_response()),
        _json_response(_search_response([raw], total=42)),
    ])
    result = client.search_items("test")

    assert isinstance(result, SearchResult)
    assert result.total == 42
    assert len(result.items) == 1
    item = result.items[0]
    assert isinstance(item, ItemSummary)
    assert item.item_id == "v1|123|0"
    assert item.title == "Test Item"
    assert item.price == 9.99
    assert item.currency == "USD"
    assert item.condition == "New"
    assert item.item_url == "https://www.ebay.com/itm/123"
    assert item.image_url == "https://i.ebayimg.com/img.jpg"


def test_search_items_empty_response():
    client, _ = _make_client([
        _json_response(_token_response()),
        _json_response({"total": 0}),
    ])
    result = client.search_items("xyzzy-nonexistent")
    assert result.total == 0
    assert result.items == []


def test_search_items_http_error_raises():
    client, _ = _make_client([
        _json_response(_token_response()),
        httpx.Response(429),
    ])
    with pytest.raises(httpx.HTTPStatusError):
        client.search_items("fail")


# ---------------------------------------------------------------------------
# get_item
# ---------------------------------------------------------------------------

def test_get_item_url():
    client, transport = _make_client([
        _json_response(_token_response()),
        _json_response({"itemId": "v1|999|0", "title": "Widget"}),
    ])
    client.get_item("v1|999|0")

    req = transport.requests[1]
    assert "/item/v1%7C999%7C0" in str(req.url) or "v1|999|0" in str(req.url)


def test_get_item_returns_dict():
    body = {"itemId": "v1|1|0", "title": "Gadget", "price": {"value": "19.99"}}
    client, _ = _make_client([
        _json_response(_token_response()),
        _json_response(body),
    ])
    result = client.get_item("v1|1|0")
    assert result["title"] == "Gadget"


def test_get_item_http_error_raises():
    client, _ = _make_client([
        _json_response(_token_response()),
        httpx.Response(404),
    ])
    with pytest.raises(httpx.HTTPStatusError):
        client.get_item("v1|bad|0")


# ---------------------------------------------------------------------------
# _parse_summary helper
# ---------------------------------------------------------------------------

def test_parse_summary_full():
    raw = _item_summary_raw()
    item = _parse_summary(raw)
    assert item.price == 9.99
    assert item.currency == "USD"


def test_parse_summary_missing_price():
    raw = _item_summary_raw()
    del raw["price"]
    item = _parse_summary(raw)
    assert item.price is None
    assert item.currency is None


def test_parse_summary_missing_image():
    raw = _item_summary_raw()
    del raw["image"]
    item = _parse_summary(raw)
    assert item.image_url is None


def test_parse_summary_partial_price():
    raw = _item_summary_raw()
    raw["price"] = {"currency": "EUR"}  # no "value" key
    item = _parse_summary(raw)
    assert item.price is None
    assert item.currency == "EUR"


# ---------------------------------------------------------------------------
# CloudSettings env loading
# ---------------------------------------------------------------------------

def test_settings_from_env_ebay(monkeypatch):
    monkeypatch.setenv("EBAY_APP_ID", "env-app")
    monkeypatch.setenv("EBAY_CERT_ID", "env-cert")
    monkeypatch.setenv("EBAY_SANDBOX", "true")
    settings = CloudSettings.from_env()
    assert settings.ebay_app_id == "env-app"
    assert settings.ebay_cert_id == "env-cert"
    assert settings.ebay_sandbox is True


def test_settings_from_env_ebay_absent(monkeypatch):
    monkeypatch.delenv("EBAY_APP_ID", raising=False)
    monkeypatch.delenv("EBAY_CERT_ID", raising=False)
    monkeypatch.delenv("EBAY_SANDBOX", raising=False)
    settings = CloudSettings.from_env()
    assert settings.ebay_app_id is None
    assert settings.ebay_cert_id is None
    assert settings.ebay_sandbox is False
