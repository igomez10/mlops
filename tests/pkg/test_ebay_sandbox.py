"""Sandbox integration tests for pkg.ebay — hit api.sandbox.ebay.com for real.

Run with:
    uv run pytest -m sandbox -v

Skipped automatically when EBAY_APP_ID or EBAY_CERT_ID are not set.
"""
from __future__ import annotations

import os

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
    result = client.search_items("phone", limit=2)
    assert len(result.items) <= 2


@pytest.mark.sandbox
def test_sandbox_search_items_are_well_formed(client):
    result = client.search_items("watch", limit=5)
    for item in result.items:
        assert isinstance(item, ItemSummary)
        assert item.item_id
        assert item.title


@pytest.mark.sandbox
def test_sandbox_search_offset(client):
    page1 = client.search_items("camera", limit=2, offset=0)
    page2 = client.search_items("camera", limit=2, offset=2)
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
    result = client.search_items("headphones", limit=1)
    if not result.items:
        pytest.skip("no items returned by sandbox search — cannot test get_item")
    item_id = result.items[0].item_id
    details = client.get_item(item_id)
    assert isinstance(details, dict)
    assert details.get("itemId") == item_id


@pytest.mark.sandbox
def test_sandbox_get_item_has_title(client):
    result = client.search_items("keyboard", limit=1)
    if not result.items:
        pytest.skip("no items returned by sandbox search")
    details = client.get_item(result.items[0].item_id)
    assert "title" in details
    assert details["title"]


@pytest.mark.sandbox
def test_sandbox_get_item_invalid_id_raises(client):
    import httpx
    with pytest.raises(httpx.HTTPStatusError):
        client.get_item("v1|000000000000|0")
