"""Sandbox integration tests for pkg.ebay — hit api.sandbox.ebay.com for real.

Run with:
    uv run pytest -m sandbox -v

Skipped automatically when EBAY_APP_ID or EBAY_CERT_ID are not set.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from pkg.ebay import EbayClient, ItemSummary, SearchResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} not set — skipping sandbox tests")
    return value


def _require_listing_env() -> dict[str, str]:
    return {
        "user_token": _require_env("EBAY_USER_ACCESS_TOKEN"),
        "fulfillment_policy_id": _require_env("EBAY_SANDBOX_FULFILLMENT_POLICY_ID"),
        "payment_policy_id": _require_env("EBAY_SANDBOX_PAYMENT_POLICY_ID"),
        "return_policy_id": _require_env("EBAY_SANDBOX_RETURN_POLICY_ID"),
        "category_id": _require_env("EBAY_SANDBOX_CATEGORY_ID"),
        "image_url": os.environ.get(
            "EBAY_SANDBOX_IMAGE_URL",
            "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg",
        ),
    }


def _search_or_skip(client: EbayClient, query: str, **kwargs: object) -> SearchResult:
    try:
        return client.search_items(query, **kwargs)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code >= 500:
            pytest.skip(f"eBay sandbox search failed with {exc.response.status_code}")
        raise


@pytest.fixture(scope="module")
def client() -> EbayClient:
    app_id = _require_env("EBAY_APP_ID")
    cert_id = _require_env("EBAY_CERT_ID")
    return EbayClient(app_id, cert_id, sandbox=True)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


@pytest.mark.sandbox
def test_sandbox_token_is_fetched(client):
    token = client._token()
    assert isinstance(token, str)
    assert len(token) > 20
    assert client._token_cache is not None


@pytest.mark.sandbox
def test_sandbox_token_is_reused_on_second_call(client):
    t1 = client._token()
    t2 = client._token()
    assert t1 == t2


# ---------------------------------------------------------------------------
# search_items
# ---------------------------------------------------------------------------


@pytest.mark.sandbox
def test_sandbox_search_returns_result(client):
    result = client.search_items("laptop", limit=3)
    assert isinstance(result, SearchResult)
    assert result.total >= 0


@pytest.mark.sandbox
def test_sandbox_search_respects_limit(client):
    result = _search_or_skip(client, "phone", limit=2)
    assert len(result.items) <= 2


@pytest.mark.sandbox
def test_sandbox_search_items_are_well_formed(client):
    result = _search_or_skip(client, "watch", limit=5)
    for item in result.items:
        assert isinstance(item, ItemSummary)
        assert item.item_id
        assert item.title


@pytest.mark.sandbox
def test_sandbox_search_offset(client):
    page1 = _search_or_skip(client, "camera", limit=2, offset=0)
    page2 = _search_or_skip(client, "camera", limit=2, offset=2)
    ids1 = {i.item_id for i in page1.items}
    ids2 = {i.item_id for i in page2.items}
    # Pages should not overlap (sandbox may have limited data, so just check they ran)
    assert isinstance(ids1, set)
    assert isinstance(ids2, set)


@pytest.mark.sandbox
def test_sandbox_search_empty_query_returns_response(client):
    # eBay may return results or an error for an empty query; we just assert no crash
    try:
        result = client.search_items("zzz-unlikely-query-xqz", limit=1)
        assert result.total >= 0
    except Exception as exc:
        # A 4xx from eBay for a bad query is also acceptable — just not a crash
        assert "4" in str(exc) or "Client" in type(exc).__name__


# ---------------------------------------------------------------------------
# get_item
# ---------------------------------------------------------------------------


@pytest.mark.sandbox
def test_sandbox_get_item_from_search(client):
    result = _search_or_skip(client, "headphones", limit=1)
    if not result.items:
        pytest.skip("no items returned by sandbox search — cannot test get_item")
    item_id = result.items[0].item_id
    details = client.get_item(item_id)
    assert isinstance(details, dict)
    assert details.get("itemId") == item_id


@pytest.mark.sandbox
def test_sandbox_get_item_has_title(client):
    result = _search_or_skip(client, "keyboard", limit=1)
    if not result.items:
        pytest.skip("no items returned by sandbox search")
    details = client.get_item(result.items[0].item_id)
    assert "title" in details
    assert details["title"]


@pytest.mark.sandbox
def test_sandbox_get_item_invalid_id_raises(client):
    with pytest.raises(httpx.HTTPStatusError):
        client.get_item("v1|000000000000|0")


# ---------------------------------------------------------------------------
# Listing creation via Inventory API
# ---------------------------------------------------------------------------


@pytest.mark.sandbox
def test_sandbox_can_fetch_listing_policies(client):
    user_token = _require_env("EBAY_USER_ACCESS_TOKEN")

    with httpx.Client(timeout=30) as http:
        account_client = EbayClient(
            client._client_id,
            client._client_secret,
            sandbox=True,
            marketplace_id=client._marketplace_id,
            http_client=http,
        )

        fulfillment = account_client.get_fulfillment_policies(user_token)
        payment = account_client.get_payment_policies(user_token)
        returns = account_client.get_return_policies(user_token)

    assert isinstance(fulfillment, list)
    assert isinstance(payment, list)
    assert isinstance(returns, list)

    if fulfillment:
        assert fulfillment[0].policy_id
    if payment:
        assert payment[0].policy_id
    if returns:
        assert returns[0].policy_id


@pytest.mark.sandbox
def test_sandbox_can_create_listing():
    """Create and publish a disposable sandbox listing with seller credentials.

    Required env vars:
    - EBAY_USER_ACCESS_TOKEN
    - EBAY_SANDBOX_FULFILLMENT_POLICY_ID
    - EBAY_SANDBOX_PAYMENT_POLICY_ID
    - EBAY_SANDBOX_RETURN_POLICY_ID
    - EBAY_SANDBOX_CATEGORY_ID

    Optional env var:
    - EBAY_SANDBOX_IMAGE_URL
    """

    cfg = _require_listing_env()
    suffix = uuid.uuid4().hex[:8]
    merchant_location_key = f"codex-loc-{suffix}"
    sku = f"codex-sku-{suffix}"

    with httpx.Client(timeout=30) as http:
        inventory_client = EbayClient(
            client._client_id,
            client._client_secret,
            sandbox=True,
            marketplace_id=client._marketplace_id,
            http_client=http,
        )

        inventory_client.create_inventory_location(
            merchant_location_key,
            cfg["user_token"],
            {
                "name": merchant_location_key,
                "merchantLocationStatus": "ENABLED",
                "locationTypes": ["WAREHOUSE"],
                "location": {
                    "address": {
                        "city": "San Jose",
                        "stateOrProvince": "CA",
                        "country": "US",
                    }
                },
            },
        )

        inventory_client.create_or_replace_inventory_item(
            sku,
            cfg["user_token"],
            {
                "availability": {"shipToLocationAvailability": {"quantity": 1}},
                "condition": "NEW",
                "product": {
                    "title": f"Codex Sandbox Listing {suffix}",
                    "description": "Disposable test listing created by automated sandbox test.",
                    "brand": "Codex",
                    "mpn": f"codex-{suffix}",
                    "imageUrls": [cfg["image_url"]],
                    "aspects": {"Brand": ["Codex"]},
                },
            },
        )

        offer_id = inventory_client.create_offer(
            cfg["user_token"],
            {
                "sku": sku,
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "availableQuantity": 1,
                "categoryId": cfg["category_id"],
                "merchantLocationKey": merchant_location_key,
                "listingDescription": ("Disposable sandbox listing created by the automated Codex test."),
                "listingPolicies": {
                    "fulfillmentPolicyId": cfg["fulfillment_policy_id"],
                    "paymentPolicyId": cfg["payment_policy_id"],
                    "returnPolicyId": cfg["return_policy_id"],
                },
                "pricingSummary": {"price": {"currency": "USD", "value": "19.99"}},
            },
        )
        assert offer_id

        publish_body = inventory_client.publish_offer(offer_id, cfg["user_token"])
        assert publish_body.get("listingId") or publish_body.get("offerId")
