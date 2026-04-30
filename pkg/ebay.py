from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from pkg.config import CloudSettings

_TOKEN_URL_PROD = "https://api.ebay.com/identity/v1/oauth2/token"
_TOKEN_URL_SBX = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
_BROWSE_BASE_PROD = "https://api.ebay.com/buy/browse/v1"
_BROWSE_BASE_SBX = "https://api.sandbox.ebay.com/buy/browse/v1"
_SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass
class ItemSummary:
    item_id: str
    title: str
    price: float | None
    currency: str | None
    condition: str | None
    item_url: str | None
    image_url: str | None


@dataclass
class SearchResult:
    total: int
    items: list[ItemSummary]


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float  # unix timestamp


@dataclass
class EbayClient:
    """eBay Browse API client with automatic OAuth token management.

    Inject `http_client` in tests to avoid real network calls.
    """

    _client_id: str
    _client_secret: str
    _marketplace_id: str
    _http: httpx.Client
    _token_cache: _TokenCache | None = field(default=None, repr=False)

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        sandbox: bool = False,
        marketplace_id: str = "EBAY_US",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not client_id:
            raise ValueError("client_id is required")
        if not client_secret:
            raise ValueError("client_secret is required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._marketplace_id = marketplace_id
        self._token_url = _TOKEN_URL_SBX if sandbox else _TOKEN_URL_PROD
        self._browse_base = _BROWSE_BASE_SBX if sandbox else _BROWSE_BASE_PROD
        self._http = http_client or httpx.Client(timeout=10)
        self._token_cache: _TokenCache | None = None

    @classmethod
    def from_settings(cls, settings: CloudSettings) -> EbayClient:
        if not settings.ebay_app_id:
            raise ValueError("EBAY_APP_ID must be set")
        if not settings.ebay_cert_id:
            raise ValueError("EBAY_CERT_ID must be set")
        return cls(
            client_id=settings.ebay_app_id,
            client_secret=settings.ebay_cert_id,
            sandbox=settings.ebay_sandbox,
        )

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _fetch_token(self) -> str:
        credentials = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        response = self._http.post(
            self._token_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": _SCOPE},
        )
        response.raise_for_status()
        body = response.json()
        token = body["access_token"]
        expires_in = int(body.get("expires_in", 7200))
        # Refresh 60 s early to avoid edge-case expiry during a request.
        self._token_cache = _TokenCache(
            access_token=token,
            expires_at=time.monotonic() + expires_in - 60,
        )
        return token

    def _token(self) -> str:
        if self._token_cache is None or time.monotonic() >= self._token_cache.expires_at:
            return self._fetch_token()
        return self._token_cache.access_token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_items(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        filter: str | None = None,
    ) -> SearchResult:
        """Search eBay listings. Returns up to `limit` item summaries."""
        params: dict[str, Any] = {"q": query, "limit": limit, "offset": offset}
        if filter:
            params["filter"] = filter
        response = self._http.get(
            f"{self._browse_base}/item_summary/search",
            headers=self._auth_headers(),
            params=params,
        )
        response.raise_for_status()
        body = response.json()
        items = [_parse_summary(raw) for raw in body.get("itemSummaries", [])]
        return SearchResult(total=body.get("total", len(items)), items=items)

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Fetch full item details by eBay item ID."""
        response = self._http.get(
            f"{self._browse_base}/item/{item_id}",
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return response.json()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_summary(raw: dict[str, Any]) -> ItemSummary:
    price_obj = raw.get("price") or {}
    return ItemSummary(
        item_id=raw.get("itemId", ""),
        title=raw.get("title", ""),
        price=float(price_obj["value"]) if price_obj.get("value") else None,
        currency=price_obj.get("currency"),
        condition=raw.get("condition"),
        item_url=raw.get("itemWebUrl"),
        image_url=(raw.get("image") or {}).get("imageUrl"),
    )
