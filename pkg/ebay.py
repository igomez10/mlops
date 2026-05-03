from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

if TYPE_CHECKING:
    from pkg.config import CloudSettings

_TOKEN_URL_PROD = "https://api.ebay.com/identity/v1/oauth2/token"
_TOKEN_URL_SBX = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
_AUTH_URL_PROD = "https://auth.ebay.com/oauth2/authorize"
_AUTH_URL_SBX = "https://auth.sandbox.ebay.com/oauth2/authorize"
_BROWSE_BASE_PROD = "https://api.ebay.com/buy/browse/v1"
_BROWSE_BASE_SBX = "https://api.sandbox.ebay.com/buy/browse/v1"
_INVENTORY_BASE_PROD = "https://api.ebay.com/sell/inventory/v1"
_INVENTORY_BASE_SBX = "https://api.sandbox.ebay.com/sell/inventory/v1"
_ACCOUNT_BASE_PROD = "https://api.ebay.com/sell/account/v1"
_ACCOUNT_BASE_SBX = "https://api.sandbox.ebay.com/sell/account/v1"
_TAXONOMY_BASE_PROD = "https://api.ebay.com/commerce/taxonomy/v1"
_TAXONOMY_BASE_SBX = "https://api.sandbox.ebay.com/commerce/taxonomy/v1"
_METADATA_BASE_PROD = "https://api.ebay.com/sell/metadata/v1"
_METADATA_BASE_SBX = "https://api.sandbox.ebay.com/sell/metadata/v1"
_SCOPE = "https://api.ebay.com/oauth/api_scope"
SELL_INVENTORY_SCOPE = "https://api.ebay.com/oauth/api_scope/sell.inventory"
SELL_ACCOUNT_SCOPE = "https://api.ebay.com/oauth/api_scope/sell.account"
DEFAULT_USER_SCOPES = (SELL_INVENTORY_SCOPE, SELL_ACCOUNT_SCOPE)


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
class MarketplacePolicy:
    policy_id: str
    name: str
    marketplace_id: str
    category_types: list[str]
    description: str | None = None


@dataclass
class OfferSummary:
    sku: str
    offer_id: str | None
    listing_id: str | None
    marketplace_id: str | None
    format: str | None
    available_quantity: int | None
    category_id: str | None
    merchant_location_key: str | None
    listing_description: str | None
    status: str | None
    price: float | None
    currency: str | None


@dataclass
class CategorySuggestion:
    category_id: str
    category_name: str
    category_tree_id: str
    category_tree_version: str | None
    path: list[str]


@dataclass
class ShippingServiceOption:
    description: str | None
    international_service: bool | None
    min_shipping_time: int | None
    max_shipping_time: int | None


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float  # monotonic deadline from time.monotonic()


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
        self._auth_url = _AUTH_URL_SBX if sandbox else _AUTH_URL_PROD
        self._browse_base = _BROWSE_BASE_SBX if sandbox else _BROWSE_BASE_PROD
        self._inventory_base = _INVENTORY_BASE_SBX if sandbox else _INVENTORY_BASE_PROD
        self._account_base = _ACCOUNT_BASE_SBX if sandbox else _ACCOUNT_BASE_PROD
        self._taxonomy_base = _TAXONOMY_BASE_SBX if sandbox else _TAXONOMY_BASE_PROD
        self._metadata_base = _METADATA_BASE_SBX if sandbox else _METADATA_BASE_PROD
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
        credentials = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
        response = self._http.post(
            self._token_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": _SCOPE},
        )
        self._raise_for_status(response)
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

    def _inventory_headers(self, user_token: str) -> dict[str, str]:
        if not user_token:
            raise ValueError("user_token is required")
        return {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
            "Content-Language": "en-US",
        }

    def _basic_auth_header(self) -> str:
        credentials = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
        return f"Basic {credentials}"

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body: str | None = None
            try:
                body = response.text.strip() or None
            except Exception:
                body = None
            if body:
                raise httpx.HTTPStatusError(
                    f"{exc}. Response body: {body}",
                    request=exc.request,
                    response=exc.response,
                ) from exc
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_items(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        filter_expr: str | None = None,
    ) -> SearchResult:
        """Search eBay listings. Returns up to `limit` item summaries."""
        params: dict[str, Any] = {"q": query, "limit": limit, "offset": offset}
        if filter_expr:
            params["filter"] = filter_expr
        response = self._http.get(
            f"{self._browse_base}/item_summary/search",
            headers=self._auth_headers(),
            params=params,
        )
        self._raise_for_status(response)
        body = response.json()
        items = [_parse_summary(raw) for raw in body.get("itemSummaries", [])]
        return SearchResult(total=body.get("total", len(items)), items=items)

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Fetch full item details by eBay item ID."""
        response = self._http.get(
            f"{self._browse_base}/item/{item_id}",
            headers=self._auth_headers(),
        )
        self._raise_for_status(response)
        return response.json()

    def build_user_consent_url(
        self,
        *,
        runame: str,
        state: str,
        scopes: tuple[str, ...] = DEFAULT_USER_SCOPES,
        prompt: str = "login",
    ) -> str:
        """Build the user-consent URL for the authorization code grant flow."""
        if not runame:
            raise ValueError("runame is required")
        if not scopes:
            raise ValueError("at least one scope is required")
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": runame,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state,
                "prompt": prompt,
            }
        )
        return f"{self._auth_url}?{query}"

    def exchange_authorization_code(self, code: str, *, runame: str) -> dict[str, Any]:
        """Exchange a one-time auth code for a user access token and refresh token."""
        if not code:
            raise ValueError("code is required")
        if not runame:
            raise ValueError("runame is required")
        response = self._http.post(
            self._token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": runame,
            },
        )
        self._raise_for_status(response)
        return response.json()

    def refresh_user_access_token(
        self,
        refresh_token: str,
        *,
        scopes: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Refresh a user access token using a stored refresh token."""
        if not refresh_token:
            raise ValueError("refresh_token is required")
        payload: dict[str, Any] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if scopes:
            payload["scope"] = " ".join(scopes)
        response = self._http.post(
            self._token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def create_inventory_location(
        self,
        merchant_location_key: str,
        user_token: str,
        payload: dict[str, Any],
    ) -> None:
        """Create an Inventory API location using seller auth."""
        response = self._http.post(
            f"{self._inventory_base}/location/{merchant_location_key}",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)

    def create_or_replace_inventory_item(
        self,
        sku: str,
        user_token: str,
        payload: dict[str, Any],
    ) -> None:
        """Create or replace an Inventory API item using seller auth."""
        response = self._http.put(
            f"{self._inventory_base}/inventory_item/{sku}",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)

    def get_inventory_item(
        self,
        sku: str,
        user_token: str,
    ) -> dict[str, Any]:
        if not sku:
            raise ValueError("sku is required")
        response = self._http.get(
            f"{self._inventory_base}/inventory_item/{sku}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def delete_inventory_item(
        self,
        sku: str,
        user_token: str,
    ) -> None:
        if not sku:
            raise ValueError("sku is required")
        response = self._http.delete(
            f"{self._inventory_base}/inventory_item/{sku}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)

    def create_offer_raw(self, user_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an Inventory API offer and return the raw response body."""
        response = self._http.post(
            f"{self._inventory_base}/offer",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def create_offer(self, user_token: str, payload: dict[str, Any]) -> str:
        """Create an Inventory API offer and return its offer ID."""
        body = self.create_offer_raw(user_token, payload)
        return str(body["offerId"])

    def publish_offer(self, offer_id: str, user_token: str) -> dict[str, Any]:
        """Publish an Inventory API offer."""
        response = self._http.post(
            f"{self._inventory_base}/offer/{offer_id}/publish",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def get_offer(
        self,
        offer_id: str,
        user_token: str,
    ) -> dict[str, Any]:
        if not offer_id:
            raise ValueError("offer_id is required")
        response = self._http.get(
            f"{self._inventory_base}/offer/{offer_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def update_offer(
        self,
        offer_id: str,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not offer_id:
            raise ValueError("offer_id is required")
        response = self._http.put(
            f"{self._inventory_base}/offer/{offer_id}",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def delete_offer(
        self,
        offer_id: str,
        user_token: str,
    ) -> None:
        if not offer_id:
            raise ValueError("offer_id is required")
        response = self._http.delete(
            f"{self._inventory_base}/offer/{offer_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)

    def withdraw_offer(
        self,
        offer_id: str,
        user_token: str,
    ) -> dict[str, Any]:
        if not offer_id:
            raise ValueError("offer_id is required")
        response = self._http.post(
            f"{self._inventory_base}/offer/{offer_id}/withdraw",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def get_inventory_items(
        self,
        user_token: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[str], str | None]:
        """List seller inventory SKUs and return the pagination cursor URL if present."""
        body = self.get_inventory_items_raw(
            user_token,
            limit=limit,
            offset=offset,
        )
        skus = [str(raw.get("sku") or "") for raw in body.get("inventoryItems") or [] if str(raw.get("sku") or "")]
        next_url = str(body.get("next")) if body.get("next") else None
        return skus, next_url

    def get_inventory_items_raw(
        self,
        user_token: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List seller inventory items and return the raw API response."""
        response = self._http.get(
            f"{self._inventory_base}/inventory_item",
            headers=self._inventory_headers(user_token),
            params={"limit": str(limit), "offset": str(offset)},
        )
        self._raise_for_status(response)
        return response.json()

    def get_offers(
        self,
        user_token: str,
        *,
        sku: str,
        marketplace_id: str | None = None,
    ) -> list[OfferSummary]:
        """List seller offers for a SKU."""
        body = self.get_offers_raw(
            user_token,
            sku=sku,
            marketplace_id=marketplace_id,
        )
        return [_parse_offer(raw) for raw in body.get("offers") or []]

    def get_offers_raw(
        self,
        user_token: str,
        *,
        sku: str,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        """List seller offers for a SKU and return the raw API response."""
        if not sku:
            raise ValueError("sku is required")
        params: dict[str, str] = {"sku": sku}
        if marketplace_id:
            params["marketplace_id"] = marketplace_id
        response = self._http.get(
            f"{self._inventory_base}/offer",
            headers=self._inventory_headers(user_token),
            params=params,
        )
        self._raise_for_status(response)
        return response.json()

    def get_default_category_tree_id(self, *, marketplace_id: str | None = None) -> str:
        params = {"marketplace_id": marketplace_id or self._marketplace_id}
        response = self._http.get(
            f"{self._taxonomy_base}/get_default_category_tree_id",
            headers={"Authorization": f"Bearer {self._token()}"},
            params=params,
        )
        self._raise_for_status(response)
        body = response.json()
        return str(body["categoryTreeId"])

    def get_category_suggestions(
        self,
        query: str,
        *,
        marketplace_id: str | None = None,
        category_tree_id: str | None = None,
        accept_language: str | None = None,
    ) -> list[CategorySuggestion]:
        body = self.get_category_suggestions_raw(
            query,
            marketplace_id=marketplace_id,
            category_tree_id=category_tree_id,
            accept_language=accept_language,
        )
        tree_id = str(body.get("categoryTreeId") or "")
        tree_version = str(body.get("categoryTreeVersion")) if body.get("categoryTreeVersion") is not None else None
        return [
            _parse_category_suggestion(
                raw,
                category_tree_id=tree_id,
                category_tree_version=tree_version,
            )
            for raw in body.get("categorySuggestions") or []
        ]

    def get_category_suggestions_raw(
        self,
        query: str,
        *,
        marketplace_id: str | None = None,
        category_tree_id: str | None = None,
        accept_language: str | None = None,
    ) -> dict[str, Any]:
        if not query:
            raise ValueError("query is required")
        tree_id = category_tree_id or self.get_default_category_tree_id(marketplace_id=marketplace_id)
        headers = {"Authorization": f"Bearer {self._token()}"}
        if accept_language:
            headers["Accept-Language"] = accept_language
        response = self._http.get(
            f"{self._taxonomy_base}/category_tree/{tree_id}/get_category_suggestions",
            headers=headers,
            params={"q": query},
        )
        self._raise_for_status(response)
        return response.json()

    def get_shipping_services(
        self,
        *,
        marketplace_id: str | None = None,
    ) -> list[ShippingServiceOption]:
        body = self.get_shipping_services_raw(
            marketplace_id=marketplace_id,
        )
        return [_parse_shipping_service_option(raw) for raw in body.get("shippingServices") or []]

    def get_shipping_services_raw(
        self,
        *,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_marketplace = marketplace_id or self._marketplace_id
        response = self._http.get(
            f"{self._metadata_base}/shipping/marketplace/{resolved_marketplace}/get_shipping_services",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        self._raise_for_status(response)
        return response.json()

    def get_fulfillment_policies(
        self,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> list[MarketplacePolicy]:
        body = self.get_fulfillment_policies_raw(
            user_token,
            marketplace_id=marketplace_id,
        )
        params_marketplace = marketplace_id or self._marketplace_id
        return [
            MarketplacePolicy(
                policy_id=str(raw["fulfillmentPolicyId"]),
                name=str(raw.get("name") or ""),
                marketplace_id=str(raw.get("marketplaceId") or params_marketplace),
                category_types=[str(item.get("name") or "") for item in raw.get("categoryTypes") or []],
                description=(str(raw.get("description")) if raw.get("description") is not None else None),
            )
            for raw in body.get("fulfillmentPolicies") or []
        ]

    def get_fulfillment_policies_raw(
        self,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"marketplace_id": marketplace_id or self._marketplace_id}
        response = self._http.get(
            f"{self._account_base}/fulfillment_policy",
            headers=self._inventory_headers(user_token),
            params=params,
        )
        self._raise_for_status(response)
        return response.json()

    def get_fulfillment_policy(
        self,
        policy_id: str,
        user_token: str,
    ) -> dict[str, Any]:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.get(
            f"{self._account_base}/fulfillment_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def create_fulfillment_policy(
        self,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._http.post(
            f"{self._account_base}/fulfillment_policy/",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def update_fulfillment_policy(
        self,
        policy_id: str,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.put(
            f"{self._account_base}/fulfillment_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def delete_fulfillment_policy(
        self,
        policy_id: str,
        user_token: str,
    ) -> None:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.delete(
            f"{self._account_base}/fulfillment_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)

    def get_opted_in_programs(self, user_token: str) -> list[dict[str, Any]]:
        response = self._http.get(
            f"{self._account_base}/program/get_opted_in_programs",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        body = response.json()
        return list(body.get("programs") or [])

    def opt_in_to_program(self, user_token: str, program_type: str) -> None:
        if not program_type:
            raise ValueError("program_type is required")
        response = self._http.post(
            f"{self._account_base}/program/opt_in",
            headers=self._inventory_headers(user_token),
            json={"programType": program_type},
        )
        self._raise_for_status(response)

    def get_payment_policies(
        self,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> list[MarketplacePolicy]:
        body = self.get_payment_policies_raw(
            user_token,
            marketplace_id=marketplace_id,
        )
        params_marketplace = marketplace_id or self._marketplace_id
        return [
            MarketplacePolicy(
                policy_id=str(raw["paymentPolicyId"]),
                name=str(raw.get("name") or ""),
                marketplace_id=str(raw.get("marketplaceId") or params_marketplace),
                category_types=[str(item.get("name") or "") for item in raw.get("categoryTypes") or []],
                description=(str(raw.get("description")) if raw.get("description") is not None else None),
            )
            for raw in body.get("paymentPolicies") or []
        ]

    def get_payment_policies_raw(
        self,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"marketplace_id": marketplace_id or self._marketplace_id}
        response = self._http.get(
            f"{self._account_base}/payment_policy",
            headers=self._inventory_headers(user_token),
            params=params,
        )
        self._raise_for_status(response)
        return response.json()

    def get_payment_policy(
        self,
        policy_id: str,
        user_token: str,
    ) -> dict[str, Any]:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.get(
            f"{self._account_base}/payment_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def create_payment_policy(
        self,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._http.post(
            f"{self._account_base}/payment_policy/",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def update_payment_policy(
        self,
        policy_id: str,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.put(
            f"{self._account_base}/payment_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def delete_payment_policy(
        self,
        policy_id: str,
        user_token: str,
    ) -> None:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.delete(
            f"{self._account_base}/payment_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)

    def get_return_policies(
        self,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> list[MarketplacePolicy]:
        body = self.get_return_policies_raw(
            user_token,
            marketplace_id=marketplace_id,
        )
        params_marketplace = marketplace_id or self._marketplace_id
        return [
            MarketplacePolicy(
                policy_id=str(raw["returnPolicyId"]),
                name=str(raw.get("name") or ""),
                marketplace_id=str(raw.get("marketplaceId") or params_marketplace),
                category_types=[str(item.get("name") or "") for item in raw.get("categoryTypes") or []],
                description=(str(raw.get("description")) if raw.get("description") is not None else None),
            )
            for raw in body.get("returnPolicies") or []
        ]

    def get_return_policies_raw(
        self,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"marketplace_id": marketplace_id or self._marketplace_id}
        response = self._http.get(
            f"{self._account_base}/return_policy",
            headers=self._inventory_headers(user_token),
            params=params,
        )
        self._raise_for_status(response)
        return response.json()

    def get_return_policy(
        self,
        policy_id: str,
        user_token: str,
    ) -> dict[str, Any]:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.get(
            f"{self._account_base}/return_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)
        return response.json()

    def create_return_policy(
        self,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._http.post(
            f"{self._account_base}/return_policy/",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def update_return_policy(
        self,
        policy_id: str,
        user_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.put(
            f"{self._account_base}/return_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    def delete_return_policy(
        self,
        policy_id: str,
        user_token: str,
    ) -> None:
        if not policy_id:
            raise ValueError("policy_id is required")
        response = self._http.delete(
            f"{self._account_base}/return_policy/{policy_id}",
            headers=self._inventory_headers(user_token),
        )
        self._raise_for_status(response)

    def _get_policies(
        self,
        path: str,
        list_key: str,
        id_key: str,
        user_token: str,
        *,
        marketplace_id: str | None = None,
    ) -> list[MarketplacePolicy]:
        params: dict[str, str] = {"marketplace_id": marketplace_id or self._marketplace_id}
        response = self._http.get(
            f"{self._account_base}/{path}",
            headers=self._inventory_headers(user_token),
            params=params,
        )
        self._raise_for_status(response)
        body = response.json()
        return [
            MarketplacePolicy(
                policy_id=str(raw[id_key]),
                name=str(raw.get("name") or ""),
                marketplace_id=str(raw.get("marketplaceId") or params["marketplace_id"]),
                category_types=[str(item.get("name") or "") for item in raw.get("categoryTypes") or []],
                description=(str(raw.get("description")) if raw.get("description") is not None else None),
            )
            for raw in body.get(list_key, [])
        ]


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


def _parse_offer(raw: dict[str, Any]) -> OfferSummary:
    pricing_summary = raw.get("pricingSummary") or {}
    price_obj = pricing_summary.get("price") or {}
    raw_listing = raw.get("listing") or {}
    raw_qty = raw.get("availableQuantity")
    return OfferSummary(
        sku=str(raw.get("sku") or ""),
        offer_id=(str(raw.get("offerId")) if raw.get("offerId") is not None else None),
        listing_id=(
            str(raw.get("listingId"))
            if raw.get("listingId") is not None
            else (str(raw_listing.get("listingId")) if raw_listing.get("listingId") is not None else None)
        ),
        marketplace_id=(str(raw.get("marketplaceId")) if raw.get("marketplaceId") is not None else None),
        format=str(raw.get("format")) if raw.get("format") is not None else None,
        available_quantity=int(raw_qty) if raw_qty is not None else None,
        category_id=(str(raw.get("categoryId")) if raw.get("categoryId") is not None else None),
        merchant_location_key=(
            str(raw.get("merchantLocationKey")) if raw.get("merchantLocationKey") is not None else None
        ),
        listing_description=(str(raw.get("listingDescription")) if raw.get("listingDescription") is not None else None),
        status=(
            str(raw.get("status"))
            if raw.get("status") is not None
            else (str(raw_listing.get("status")) if raw_listing.get("status") is not None else None)
        ),
        price=float(price_obj["value"]) if price_obj.get("value") else None,
        currency=price_obj.get("currency"),
    )


def _parse_category_suggestion(
    raw: dict[str, Any],
    *,
    category_tree_id: str,
    category_tree_version: str | None,
) -> CategorySuggestion:
    category = raw.get("category") or {}
    ancestors = raw.get("categoryTreeNodeAncestors") or []
    path = [
        str(item.get("category", {}).get("categoryName") or "")
        for item in ancestors
        if str(item.get("category", {}).get("categoryName") or "")
    ]
    category_name = str(category.get("categoryName") or "")
    if category_name:
        path.append(category_name)
    return CategorySuggestion(
        category_id=str(category.get("categoryId") or ""),
        category_name=category_name,
        category_tree_id=category_tree_id,
        category_tree_version=category_tree_version,
        path=path,
    )


def _parse_shipping_service_option(raw: dict[str, Any]) -> ShippingServiceOption:
    return ShippingServiceOption(
        description=(str(raw.get("description")) if raw.get("description") is not None else None),
        international_service=(
            bool(raw.get("internationalService")) if raw.get("internationalService") is not None else None
        ),
        min_shipping_time=(int(raw.get("minShippingTime")) if raw.get("minShippingTime") is not None else None),
        max_shipping_time=(int(raw.get("maxShippingTime")) if raw.get("maxShippingTime") is not None else None),
    )
