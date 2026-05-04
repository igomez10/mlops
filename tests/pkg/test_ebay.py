"""Unit tests for pkg.ebay — all network calls are intercepted via httpx.MockTransport."""

from __future__ import annotations

import base64
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from pkg.config import CloudSettings
from pkg.ebay import (
    DEFAULT_USER_SCOPES,
    SELL_ACCOUNT_SCOPE,
    SELL_INVENTORY_SCOPE,
    CategorySuggestion,
    EbayClient,
    ItemSummary,
    MarketplacePolicy,
    OfferSummary,
    SearchResult,
    ShippingServiceOption,
    _parse_summary,
)

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


def _empty_response(status_code: int = 204) -> httpx.Response:
    return httpx.Response(status_code)


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
    client_id = getattr(client, "_client_id", getattr(client, "client_id", None))
    client_secret = getattr(client, "_client_secret", getattr(client, "client_secret", None))
    assert client_id == "test-app-id"
    assert client_secret == "test-cert-id"
    assert "test-cert-id" not in repr(client)


def test_client_close_closes_owned_http_client():
    client = EbayClient("app-id", "cert-id")
    client.close()
    assert client._http.is_closed is True


def test_ebay_client_uses_alternate_urls_when_not_production():
    transport = _MockTransport(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
        ]
    )
    http = httpx.Client(transport=transport)
    client = EbayClient("a", "b", sandbox=True, http_client=http)
    client.search_items("test")

    assert "sandbox.ebay.com" in str(transport.requests[0].url)
    assert "sandbox.ebay.com" in str(transport.requests[1].url)


def test_production_uses_production_urls():
    transport = _MockTransport(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
        ]
    )
    http = httpx.Client(transport=transport)
    client = EbayClient("a", "b", sandbox=False, http_client=http)
    client.search_items("test")

    assert "sandbox" not in str(transport.requests[0].url)
    assert "sandbox" not in str(transport.requests[1].url)


def test_from_settings_uses_alternate_urls_when_not_production():
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
    client, transport = _make_client(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
        ]
    )
    client.search_items("laptop")

    token_req = transport.requests[0]
    assert token_req.method == "POST"
    assert "identity/v1/oauth2/token" in str(token_req.url)

    expected = base64.b64encode(b"app-id:cert-id").decode()
    assert token_req.headers["Authorization"] == f"Basic {expected}"
    assert token_req.headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_token_is_cached_across_calls():
    client, transport = _make_client(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
            _json_response(_search_response()),
        ]
    )
    client.search_items("a")
    client.search_items("b")

    token_requests = [r for r in transport.requests if "oauth2/token" in str(r.url)]
    assert len(token_requests) == 1


def test_expired_token_is_refreshed(monkeypatch):
    client, transport = _make_client(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
            _json_response(_token_response("tok-new")),
            _json_response(_search_response()),
        ]
    )
    client.search_items("a")

    # Simulate token expiry
    client._token_cache.expires_at = time.monotonic() - 1

    client.search_items("b")

    token_requests = [r for r in transport.requests if "oauth2/token" in str(r.url)]
    assert len(token_requests) == 2


def test_token_refresh_buffer_does_not_immediately_expire_short_lived_tokens():
    client, _ = _make_client(
        [
            _json_response(_token_response(expires_in=30)),
            _json_response(_search_response()),
        ]
    )
    before = time.monotonic()
    client.search_items("a")

    assert client._token_cache is not None
    assert client._token_cache.expires_at > before


def test_token_forwarded_as_bearer_in_search():
    client, transport = _make_client(
        [
            _json_response(_token_response("my-token")),
            _json_response(_search_response()),
        ]
    )
    client.search_items("watch")

    search_req = transport.requests[1]
    assert search_req.headers["Authorization"] == "Bearer my-token"


# ---------------------------------------------------------------------------
# search_items
# ---------------------------------------------------------------------------


def test_search_items_url_and_params():
    client, transport = _make_client(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
        ]
    )
    client.search_items("iphone", limit=5, offset=10)

    req = transport.requests[1]
    assert "/item_summary/search" in str(req.url)
    assert "q=iphone" in str(req.url)
    assert "limit=5" in str(req.url)
    assert "offset=10" in str(req.url)


def test_search_items_with_filter():
    client, transport = _make_client(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
        ]
    )
    client.search_items("shoes", filter_expr="price:[10..50]")

    req = transport.requests[1]
    assert "filter=" in str(req.url)


def test_search_items_marketplace_header():
    transport = _MockTransport(
        [
            _json_response(_token_response()),
            _json_response(_search_response()),
        ]
    )
    http = httpx.Client(transport=transport)
    client = EbayClient("a", "b", marketplace_id="EBAY_GB", http_client=http)
    client.search_items("tea")

    req = transport.requests[1]
    assert req.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"


def test_search_items_returns_result():
    raw = _item_summary_raw()
    client, _ = _make_client(
        [
            _json_response(_token_response()),
            _json_response(_search_response([raw], total=42)),
        ]
    )
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
    client, _ = _make_client(
        [
            _json_response(_token_response()),
            _json_response({"total": 0}),
        ]
    )
    result = client.search_items("xyzzy-nonexistent")
    assert result.total == 0
    assert result.items == []


def test_search_items_http_error_raises():
    client, _ = _make_client(
        [
            _json_response(_token_response()),
            httpx.Response(429),
        ]
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.search_items("fail")


def test_http_errors_include_response_body():
    client, _ = _make_client(
        [
            httpx.Response(400, json={"errors": [{"message": "Category ID is invalid"}]}),
        ]
    )
    with pytest.raises(httpx.HTTPStatusError, match="Category ID is invalid"):
        client.create_offer("user-token-123", {"sku": "sku-1"})


# ---------------------------------------------------------------------------
# get_item
# ---------------------------------------------------------------------------


def test_get_item_url():
    client, transport = _make_client(
        [
            _json_response(_token_response()),
            _json_response({"itemId": "v1|999|0", "title": "Widget"}),
        ]
    )
    client.get_item("v1|999|0")

    req = transport.requests[1]
    assert "/item/v1%7C999%7C0" in str(req.url) or "v1|999|0" in str(req.url)


def test_get_item_returns_dict():
    body = {"itemId": "v1|1|0", "title": "Gadget", "price": {"value": "19.99"}}
    client, _ = _make_client(
        [
            _json_response(_token_response()),
            _json_response(body),
        ]
    )
    result = client.get_item("v1|1|0")
    assert result["title"] == "Gadget"


def test_get_item_http_error_raises():
    client, _ = _make_client(
        [
            _json_response(_token_response()),
            httpx.Response(404),
        ]
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.get_item("v1|bad|0")


# ---------------------------------------------------------------------------
# Inventory API helpers
# ---------------------------------------------------------------------------


def test_create_inventory_location_uses_seller_headers_and_payload():
    client, transport = _make_client([_empty_response()])

    client.create_inventory_location(
        "loc-1",
        "user-token-123",
        {
            "name": "loc-1",
            "merchantLocationStatus": "ENABLED",
            "locationTypes": ["WAREHOUSE"],
            "location": {"address": {"city": "San Jose", "stateOrProvince": "CA", "country": "US"}},
        },
    )

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/inventory/v1/location/loc-1" in str(req.url)
    assert req.headers["Authorization"] == "Bearer user-token-123"
    assert req.headers["Content-Type"] == "application/json"
    assert req.headers["Content-Language"] == "en-US"
    assert b'"name":"loc-1"' in req.content


def test_create_or_replace_inventory_item_uses_put():
    client, transport = _make_client([_empty_response()])

    client.create_or_replace_inventory_item(
        "sku-1",
        "user-token-123",
        {"condition": "NEW", "availability": {"shipToLocationAvailability": {"quantity": 1}}},
    )

    req = transport.requests[0]
    assert req.method == "PUT"
    assert "/sell/inventory/v1/inventory_item/sku-1" in str(req.url)
    assert b'"condition":"NEW"' in req.content


def test_create_offer_returns_offer_id():
    client, transport = _make_client([_json_response({"offerId": "offer-123"})])

    offer_id = client.create_offer(
        "user-token-123",
        {"sku": "sku-1", "marketplaceId": "EBAY_US", "format": "FIXED_PRICE"},
    )

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/inventory/v1/offer" in str(req.url)
    assert offer_id == "offer-123"


def test_publish_offer_returns_response_body():
    client, transport = _make_client([_json_response({"listingId": "listing-123"})])

    body = client.publish_offer("offer-123", "user-token-123")

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/inventory/v1/offer/offer-123/publish" in str(req.url)
    assert body["listingId"] == "listing-123"


def test_get_offer_returns_payload():
    client, transport = _make_client([_json_response({"offerId": "offer-123", "sku": "sku-1"})])

    body = client.get_offer("offer-123", "user-token-123")

    req = transport.requests[0]
    assert req.method == "GET"
    assert "/sell/inventory/v1/offer/offer-123" in str(req.url)
    assert body["offerId"] == "offer-123"


def test_update_offer_puts_payload():
    client, transport = _make_client([_json_response({"offerId": "offer-123", "availableQuantity": 2})])

    body = client.update_offer(
        "offer-123",
        "user-token-123",
        {"sku": "sku-1", "marketplaceId": "EBAY_US", "format": "FIXED_PRICE"},
    )

    req = transport.requests[0]
    assert req.method == "PUT"
    assert "/sell/inventory/v1/offer/offer-123" in str(req.url)
    assert b'"sku":"sku-1"' in req.content
    assert body["offerId"] == "offer-123"


def test_delete_offer_uses_delete():
    client, transport = _make_client([_empty_response()])

    client.delete_offer("offer-123", "user-token-123")

    req = transport.requests[0]
    assert req.method == "DELETE"
    assert "/sell/inventory/v1/offer/offer-123" in str(req.url)


def test_withdraw_offer_returns_response_body():
    client, transport = _make_client([_json_response({"offerId": "offer-123", "status": "UNPUBLISHED"})])

    body = client.withdraw_offer("offer-123", "user-token-123")

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/inventory/v1/offer/offer-123/withdraw" in str(req.url)
    assert body["status"] == "UNPUBLISHED"


def test_get_inventory_items_returns_skus_and_next():
    client, transport = _make_client(
        [
            _json_response(
                {
                    "inventoryItems": [{"sku": "sku-1"}, {"sku": "sku-2"}],
                    "next": "https://api.ebay.com/sell/inventory/v1/inventory_item?offset=2",
                }
            )
        ]
    )

    skus, next_url = client.get_inventory_items("user-token-123", limit=2, offset=0)

    req = transport.requests[0]
    assert "/sell/inventory/v1/inventory_item" in str(req.url)
    assert "limit=2" in str(req.url)
    assert "offset=0" in str(req.url)
    assert req.headers["Authorization"] == "Bearer user-token-123"
    assert skus == ["sku-1", "sku-2"]
    assert next_url == "https://api.ebay.com/sell/inventory/v1/inventory_item?offset=2"


def test_get_inventory_item_returns_payload():
    client, transport = _make_client([_json_response({"sku": "sku-1", "condition": "NEW"})])

    body = client.get_inventory_item("sku-1", "user-token-123")

    req = transport.requests[0]
    assert req.method == "GET"
    assert "/sell/inventory/v1/inventory_item/sku-1" in str(req.url)
    assert body["sku"] == "sku-1"


def test_delete_inventory_item_uses_delete():
    client, transport = _make_client([_empty_response()])

    client.delete_inventory_item("sku-1", "user-token-123")

    req = transport.requests[0]
    assert req.method == "DELETE"
    assert "/sell/inventory/v1/inventory_item/sku-1" in str(req.url)


def test_get_offers_returns_offer_summaries():
    client, transport = _make_client(
        [
            _json_response(
                {
                    "offers": [
                        {
                            "sku": "sku-1",
                            "offerId": "offer-123",
                            "listingId": "listing-456",
                            "marketplaceId": "EBAY_US",
                            "format": "FIXED_PRICE",
                            "availableQuantity": 3,
                            "categoryId": "9355",
                            "merchantLocationKey": "loc-1",
                            "listingDescription": "Test listing",
                            "status": "PUBLISHED",
                            "pricingSummary": {"price": {"value": "19.99", "currency": "USD"}},
                        }
                    ]
                }
            )
        ]
    )

    offers = client.get_offers("user-token-123", sku="sku-1")

    req = transport.requests[0]
    assert "/sell/inventory/v1/offer" in str(req.url)
    assert "sku=sku-1" in str(req.url)
    assert offers == [
        OfferSummary(
            sku="sku-1",
            offer_id="offer-123",
            listing_id="listing-456",
            marketplace_id="EBAY_US",
            format="FIXED_PRICE",
            available_quantity=3,
            category_id="9355",
            merchant_location_key="loc-1",
            listing_description="Test listing",
            status="PUBLISHED",
            price=19.99,
            currency="USD",
        )
    ]


def test_get_default_category_tree_id_uses_taxonomy_api():
    client, transport = _make_client(
        [
            _json_response(_token_response("app-token")),
            _json_response({"categoryTreeId": "0", "categoryTreeVersion": "123"}),
        ]
    )

    tree_id = client.get_default_category_tree_id(marketplace_id="EBAY_US")

    req = transport.requests[1]
    assert "/commerce/taxonomy/v1/get_default_category_tree_id" in str(req.url)
    assert "marketplace_id=EBAY_US" in str(req.url)
    assert req.headers["Authorization"] == "Bearer app-token"
    assert tree_id == "0"


def test_get_category_suggestions_returns_summaries():
    client, transport = _make_client(
        [
            _json_response(_token_response("app-token")),
            _json_response({"categoryTreeId": "0", "categoryTreeVersion": "123"}),
            _json_response(
                {
                    "categoryTreeId": "0",
                    "categoryTreeVersion": "123",
                    "categorySuggestions": [
                        {
                            "category": {
                                "categoryId": "9355",
                                "categoryName": "Cell Phones & Smartphones",
                            },
                            "categoryTreeNodeAncestors": [
                                {"category": {"categoryName": "Electronics"}},
                                {"category": {"categoryName": "Cell Phones"}},
                            ],
                        }
                    ],
                }
            ),
        ]
    )

    suggestions = client.get_category_suggestions(
        "iphone",
        marketplace_id="EBAY_US",
        accept_language="en-US",
    )

    req = transport.requests[2]
    assert "/commerce/taxonomy/v1/category_tree/0/get_category_suggestions" in str(req.url)
    assert "q=iphone" in str(req.url)
    assert req.headers["Authorization"] == "Bearer app-token"
    assert req.headers["Accept-Language"] == "en-US"
    assert suggestions == [
        CategorySuggestion(
            category_id="9355",
            category_name="Cell Phones & Smartphones",
            category_tree_id="0",
            category_tree_version="123",
            path=["Electronics", "Cell Phones", "Cell Phones & Smartphones"],
        )
    ]


def test_get_fulfillment_policy_returns_payload():
    client, transport = _make_client([_json_response({"fulfillmentPolicyId": "policy-1", "name": "Policy 1"})])

    body = client.get_fulfillment_policy("policy-1", "user-token-123")

    req = transport.requests[0]
    assert "/sell/account/v1/fulfillment_policy/policy-1" in str(req.url)
    assert req.headers["Authorization"] == "Bearer user-token-123"
    assert body["fulfillmentPolicyId"] == "policy-1"


def test_create_fulfillment_policy_posts_payload():
    client, transport = _make_client([_json_response({"fulfillmentPolicyId": "policy-1", "name": "Policy 1"})])

    body = client.create_fulfillment_policy(
        "user-token-123",
        {"name": "Policy 1", "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]},
    )

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/account/v1/fulfillment_policy/" in str(req.url)
    assert b'"name":"Policy 1"' in req.content
    assert body["fulfillmentPolicyId"] == "policy-1"


def test_update_fulfillment_policy_puts_payload():
    client, transport = _make_client([_json_response({"fulfillmentPolicyId": "policy-1", "name": "Updated Policy"})])

    body = client.update_fulfillment_policy(
        "policy-1",
        "user-token-123",
        {"name": "Updated Policy", "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]},
    )

    req = transport.requests[0]
    assert req.method == "PUT"
    assert "/sell/account/v1/fulfillment_policy/policy-1" in str(req.url)
    assert b'"name":"Updated Policy"' in req.content
    assert body["name"] == "Updated Policy"


def test_delete_fulfillment_policy_uses_delete():
    client, transport = _make_client([_empty_response()])

    client.delete_fulfillment_policy("policy-1", "user-token-123")

    req = transport.requests[0]
    assert req.method == "DELETE"
    assert "/sell/account/v1/fulfillment_policy/policy-1" in str(req.url)


def test_get_payment_policies_returns_raw_payload():
    client, transport = _make_client(
        [_json_response({"paymentPolicies": [{"paymentPolicyId": "policy-1", "name": "Policy 1"}]})]
    )

    body = client.get_payment_policies_raw("user-token-123", marketplace_id="EBAY_US")

    req = transport.requests[0]
    assert "/sell/account/v1/payment_policy" in str(req.url)
    assert "marketplace_id=EBAY_US" in str(req.url)
    assert body == {"paymentPolicies": [{"paymentPolicyId": "policy-1", "name": "Policy 1"}]}


def test_get_payment_policy_returns_payload():
    client, transport = _make_client([_json_response({"paymentPolicyId": "policy-1", "name": "Policy 1"})])

    body = client.get_payment_policy("policy-1", "user-token-123")

    req = transport.requests[0]
    assert "/sell/account/v1/payment_policy/policy-1" in str(req.url)
    assert body["paymentPolicyId"] == "policy-1"


def test_create_payment_policy_posts_payload():
    client, transport = _make_client([_json_response({"paymentPolicyId": "policy-1", "name": "Policy 1"})])

    body = client.create_payment_policy(
        "user-token-123",
        {"name": "Policy 1", "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]},
    )

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/account/v1/payment_policy/" in str(req.url)
    assert b'"name":"Policy 1"' in req.content
    assert body["paymentPolicyId"] == "policy-1"


def test_update_payment_policy_puts_payload():
    client, transport = _make_client([_json_response({"paymentPolicyId": "policy-1", "name": "Updated Policy"})])

    body = client.update_payment_policy(
        "policy-1",
        "user-token-123",
        {"name": "Updated Policy", "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]},
    )

    req = transport.requests[0]
    assert req.method == "PUT"
    assert "/sell/account/v1/payment_policy/policy-1" in str(req.url)
    assert b'"name":"Updated Policy"' in req.content
    assert body["name"] == "Updated Policy"


def test_delete_payment_policy_uses_delete():
    client, transport = _make_client([_empty_response()])

    client.delete_payment_policy("policy-1", "user-token-123")

    req = transport.requests[0]
    assert req.method == "DELETE"
    assert "/sell/account/v1/payment_policy/policy-1" in str(req.url)


def test_get_return_policies_returns_raw_payload():
    client, transport = _make_client(
        [_json_response({"returnPolicies": [{"returnPolicyId": "policy-1", "name": "Policy 1"}]})]
    )

    body = client.get_return_policies_raw("user-token-123", marketplace_id="EBAY_US")

    req = transport.requests[0]
    assert "/sell/account/v1/return_policy" in str(req.url)
    assert "marketplace_id=EBAY_US" in str(req.url)
    assert body == {"returnPolicies": [{"returnPolicyId": "policy-1", "name": "Policy 1"}]}


def test_get_return_policy_returns_payload():
    client, transport = _make_client([_json_response({"returnPolicyId": "policy-1", "name": "Policy 1"})])

    body = client.get_return_policy("policy-1", "user-token-123")

    req = transport.requests[0]
    assert "/sell/account/v1/return_policy/policy-1" in str(req.url)
    assert body["returnPolicyId"] == "policy-1"


def test_create_return_policy_posts_payload():
    client, transport = _make_client([_json_response({"returnPolicyId": "policy-1", "name": "Policy 1"})])

    body = client.create_return_policy(
        "user-token-123",
        {"name": "Policy 1", "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]},
    )

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/account/v1/return_policy/" in str(req.url)
    assert b'"name":"Policy 1"' in req.content
    assert body["returnPolicyId"] == "policy-1"


def test_update_return_policy_puts_payload():
    client, transport = _make_client([_json_response({"returnPolicyId": "policy-1", "name": "Updated Policy"})])

    body = client.update_return_policy(
        "policy-1",
        "user-token-123",
        {"name": "Updated Policy", "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]},
    )

    req = transport.requests[0]
    assert req.method == "PUT"
    assert "/sell/account/v1/return_policy/policy-1" in str(req.url)
    assert b'"name":"Updated Policy"' in req.content
    assert body["name"] == "Updated Policy"


def test_delete_return_policy_uses_delete():
    client, transport = _make_client([_empty_response()])

    client.delete_return_policy("policy-1", "user-token-123")

    req = transport.requests[0]
    assert req.method == "DELETE"
    assert "/sell/account/v1/return_policy/policy-1" in str(req.url)


def test_get_opted_in_programs_returns_programs():
    client, transport = _make_client([_json_response({"programs": [{"programType": "SELLING_POLICY_MANAGEMENT"}]})])

    body = client.get_opted_in_programs("user-token-123")

    req = transport.requests[0]
    assert req.method == "GET"
    assert "/sell/account/v1/program/get_opted_in_programs" in str(req.url)
    assert body == [{"programType": "SELLING_POLICY_MANAGEMENT"}]


def test_opt_in_to_program_posts_payload():
    client, transport = _make_client([_json_response({})])

    client.opt_in_to_program("user-token-123", "SELLING_POLICY_MANAGEMENT")

    req = transport.requests[0]
    assert req.method == "POST"
    assert "/sell/account/v1/program/opt_in" in str(req.url)
    assert b'"programType":"SELLING_POLICY_MANAGEMENT"' in req.content


def test_get_shipping_services_returns_metadata():
    client, transport = _make_client(
        [
            _json_response(_token_response("app-token")),
            _json_response(
                {
                    "shippingServices": [
                        {
                            "description": "USPS Priority Mail",
                            "internationalService": False,
                            "minShippingTime": 1,
                            "maxShippingTime": 3,
                        }
                    ]
                }
            ),
        ]
    )

    services = client.get_shipping_services(marketplace_id="EBAY_US")

    req = transport.requests[1]
    assert "/sell/metadata/v1/shipping/marketplace/EBAY_US/get_shipping_services" in str(req.url)
    assert req.headers["Authorization"] == "Bearer app-token"
    assert services == [
        ShippingServiceOption(
            description="USPS Priority Mail",
            international_service=False,
            min_shipping_time=1,
            max_shipping_time=3,
        )
    ]


def test_inventory_helpers_require_user_token():
    client, _ = _make_client([])

    with pytest.raises(ValueError, match="user_token"):
        client.create_inventory_location("loc-1", "", {})


def test_create_inventory_location_succeeds_on_201():
    client, transport = _make_client([_empty_response(201)])
    client.create_inventory_location("loc-1", "tok", {"name": "loc-1"})
    assert len(transport.requests) == 1


def test_create_inventory_location_ignores_already_exists_error():
    already_exists = _json_response(
        {"errors": [{"errorId": 25803, "domain": "API_INVENTORY", "message": "merchantLocationKey already exists."}]},
        status_code=400,
    )
    client, transport = _make_client([already_exists])
    # Should not raise even though the server returned 400
    client.create_inventory_location("loc-1", "tok", {"name": "loc-1"})
    assert len(transport.requests) == 1


def test_create_inventory_location_raises_on_other_400():
    other_error = _json_response(
        {"errors": [{"errorId": 25001, "message": "Some other error."}]},
        status_code=400,
    )
    client, _ = _make_client([other_error])
    with pytest.raises(Exception):
        client.create_inventory_location("loc-1", "tok", {"name": "loc-1"})


def test_get_valid_conditions_returns_condition_enums():
    body = {
        "itemConditionPolicies": [
            {
                "categoryId": "9355",
                "itemConditions": [
                    {"conditionDescription": "New", "conditionEnum": "NEW", "conditionId": "1000"},
                    {
                        "conditionDescription": "Used - Excellent",
                        "conditionEnum": "USED_EXCELLENT",
                        "conditionId": "3000",
                    },
                    {"conditionDescription": "Used - Good", "conditionEnum": "USED_GOOD", "conditionId": "4000"},
                ],
            }
        ]
    }
    client, transport = _make_client([_json_response(_token_response()), _json_response(body)])
    result = client.get_valid_conditions("9355", marketplace_id="EBAY_US")
    assert result == ["NEW", "USED_EXCELLENT", "USED_GOOD"]
    assert transport.requests[-1].url.params["category_id"] == "9355"


def test_get_valid_conditions_returns_empty_when_no_policies():
    client, _ = _make_client([_json_response(_token_response()), _json_response({"itemConditionPolicies": []})])
    assert client.get_valid_conditions("9355") == []


def test_get_fulfillment_policies_returns_parsed_models():
    client, transport = _make_client(
        [
            _json_response(
                {
                    "fulfillmentPolicies": [
                        {
                            "fulfillmentPolicyId": "fp-1",
                            "name": "Default shipping",
                            "marketplaceId": "EBAY_US",
                            "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                            "description": "Fast shipping",
                        }
                    ]
                }
            )
        ]
    )

    policies = client.get_fulfillment_policies("user-token-123")

    req = transport.requests[0]
    assert req.method == "GET"
    assert "/sell/account/v1/fulfillment_policy" in str(req.url)
    assert "marketplace_id=EBAY_US" in str(req.url)
    assert len(policies) == 1
    assert isinstance(policies[0], MarketplacePolicy)
    assert policies[0].policy_id == "fp-1"


def test_get_payment_policies_uses_marketplace_override():
    client, transport = _make_client([_json_response({"paymentPolicies": []})])

    client.get_payment_policies("user-token-123", marketplace_id="EBAY_GB")

    req = transport.requests[0]
    assert "/sell/account/v1/payment_policy" in str(req.url)
    assert "marketplace_id=EBAY_GB" in str(req.url)


def test_get_return_policies_requires_user_token():
    client, _ = _make_client([])

    with pytest.raises(ValueError, match="user_token"):
        client.get_return_policies("")


def test_build_user_consent_url_contains_required_params():
    client, _ = _make_client([])

    url = client.build_user_consent_url(
        runame="my-runame",
        state="state-123",
        scopes=DEFAULT_USER_SCOPES,
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert "oauth2/authorize" in url
    assert query["client_id"] == ["app-id"]
    assert query["redirect_uri"] == ["my-runame"]
    assert query["response_type"] == ["code"]
    assert query["state"] == ["state-123"]
    assert SELL_INVENTORY_SCOPE in query["scope"][0]
    assert SELL_ACCOUNT_SCOPE in query["scope"][0]


def test_exchange_authorization_code_posts_expected_form():
    client, transport = _make_client(
        [
            _json_response(
                {
                    "access_token": "user-access",
                    "refresh_token": "user-refresh",
                    "expires_in": 7200,
                    "refresh_token_expires_in": 47304000,
                    "scope": f"{SELL_INVENTORY_SCOPE} {SELL_ACCOUNT_SCOPE}",
                    "token_type": "User Access Token",
                }
            )
        ]
    )

    body = client.exchange_authorization_code("auth-code-123", runame="my-runame")

    req = transport.requests[0]
    expected = base64.b64encode(b"app-id:cert-id").decode()
    assert req.method == "POST"
    assert req.headers["Authorization"] == f"Basic {expected}"
    assert b"grant_type=authorization_code" in req.content
    assert b"code=auth-code-123" in req.content
    assert b"redirect_uri=my-runame" in req.content
    assert body["access_token"] == "user-access"


def test_refresh_user_access_token_posts_expected_form():
    client, transport = _make_client([_json_response({"access_token": "user-access-2", "expires_in": 7200})])

    body = client.refresh_user_access_token(
        "refresh-123",
        scopes=DEFAULT_USER_SCOPES,
    )

    req = transport.requests[0]
    assert req.method == "POST"
    assert b"grant_type=refresh_token" in req.content
    assert b"refresh_token=refresh-123" in req.content
    assert b"sell.inventory" in req.content
    assert body["access_token"] == "user-access-2"


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
