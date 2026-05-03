from __future__ import annotations

import json
from pathlib import Path

import pytest

from pkg.ebay_cli import main


class _FakeOffer:
    def __init__(
        self,
        *,
        sku: str,
        offer_id: str,
        listing_id: str,
        marketplace_id: str = "EBAY_US",
        format: str = "FIXED_PRICE",
        available_quantity: int = 1,
        category_id: str = "9355",
        merchant_location_key: str = "loc-1",
        listing_description: str = "desc",
        status: str = "PUBLISHED",
        price: float = 9.99,
        currency: str = "USD",
    ) -> None:
        self.sku = sku
        self.offer_id = offer_id
        self.listing_id = listing_id
        self.marketplace_id = marketplace_id
        self.format = format
        self.available_quantity = available_quantity
        self.category_id = category_id
        self.merchant_location_key = merchant_location_key
        self.listing_description = listing_description
        self.status = status
        self.price = price
        self.currency = currency


def test_cli_list_listings_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_inventory_items_raw(self, user_access_token: str, *, limit: int = 200, offset: int = 0):
            assert user_access_token == "user-token-123"
            assert limit == 50
            assert offset == 0
            return {"inventoryItems": [{"sku": "sku-1"}]}

        def get_offers_raw(self, user_access_token: str, *, sku: str):
            assert user_access_token == "user-token-123"
            assert sku == "sku-1"
            return {
                "offers": [
                    {
                        "sku": "sku-1",
                        "offerId": "offer-1",
                        "listingId": "listing-1",
                        "marketplaceId": "EBAY_US",
                        "format": "FIXED_PRICE",
                    }
                ]
            }

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "list-listings",
            "--user-access-token",
            "user-token-123",
            "--page-size",
            "50",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "listings": [
            {
                "format": "FIXED_PRICE",
                "listingId": "listing-1",
                "marketplaceId": "EBAY_US",
                "offerId": "offer-1",
                "sku": "sku-1",
            }
        ]
    }


def test_cli_suggest_categories_outputs_json(monkeypatch, capsys):
    class _FakeSuggestion:
        def __init__(self) -> None:
            self.category_id = "9355"
            self.category_name = "Cell Phones & Smartphones"
            self.category_tree_id = "0"
            self.category_tree_version = "123"
            self.path = ["Electronics", "Cell Phones", "Cell Phones & Smartphones"]

    class _FakeClient:
        def get_category_suggestions_raw(
            self,
            query: str,
            *,
            marketplace_id: str | None = None,
            accept_language: str | None = None,
        ):
            assert query == "iphone"
            assert marketplace_id == "EBAY_US"
            assert accept_language == "en-US"
            return {
                "categorySuggestions": [
                    {
                        "category": {
                            "categoryId": "9355",
                            "categoryName": "Cell Phones & Smartphones",
                        }
                    }
                ],
                "categoryTreeId": "0",
                "categoryTreeVersion": "123",
            }

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "suggest-categories",
            "--query",
            "iphone",
            "--marketplace-id",
            "EBAY_US",
            "--accept-language",
            "en-US",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "categorySuggestions": [
            {
                "category": {
                    "categoryId": "9355",
                    "categoryName": "Cell Phones & Smartphones",
                }
            }
        ],
        "categoryTreeId": "0",
        "categoryTreeVersion": "123",
    }


def test_cli_list_shipping_services_outputs_json(monkeypatch, capsys):
    class _FakeService:
        def __init__(self) -> None:
            self.description = "USPS Priority Mail"
            self.international_service = False
            self.min_shipping_time = 1
            self.max_shipping_time = 3

    class _FakeClient:
        def get_shipping_services_raw(self, *, marketplace_id: str | None = None):
            assert marketplace_id == "EBAY_US"
            return {
                "shippingServices": [
                    {
                        "description": "USPS Priority Mail",
                        "internationalService": False,
                        "minShippingTime": 1,
                        "maxShippingTime": 3,
                    }
                ]
            }

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "list-shipping-services",
            "--marketplace-id",
            "EBAY_US",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "shippingServices": [
            {
                "description": "USPS Priority Mail",
                "internationalService": False,
                "maxShippingTime": 3,
                "minShippingTime": 1,
            }
        ]
    }


def test_cli_inventory_item_commands_output_json(monkeypatch, capsys, tmp_path: Path):
    payload_file = tmp_path / "inventory-item.json"
    payload_file.write_text(
        json.dumps({"condition": "NEW", "product": {"title": "Test"}}),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def get_inventory_items_raw(self, user_access_token: str, *, limit: int = 200, offset: int = 0):
            calls.append(("list", user_access_token, limit, offset))
            return {"inventoryItems": [{"sku": "sku-1"}]}

        def get_inventory_item(self, sku: str, user_access_token: str):
            calls.append(("get", sku, user_access_token))
            return {"sku": sku, "condition": "NEW"}

        def create_or_replace_inventory_item(self, sku: str, user_access_token: str, payload: dict):
            calls.append(("upsert", sku, user_access_token, payload))

        def delete_inventory_item(self, sku: str, user_access_token: str):
            calls.append(("delete", sku, user_access_token))

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    assert main(["list-inventory-items", "--user-access-token", "user-token-123"]) == 0
    assert json.loads(capsys.readouterr().out) == {"inventoryItems": [{"sku": "sku-1"}]}

    assert main(["get-inventory-item", "--user-access-token", "user-token-123", "--sku", "sku-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"sku": "sku-1", "condition": "NEW"}

    assert main(
        [
            "create-inventory-item",
            "--user-access-token",
            "user-token-123",
            "--sku",
            "sku-1",
            "--payload-file",
            str(payload_file),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"created": True, "sku": "sku-1"}

    assert main(
        [
            "update-inventory-item",
            "--user-access-token",
            "user-token-123",
            "--sku",
            "sku-1",
            "--payload-file",
            str(payload_file),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"updated": True, "sku": "sku-1"}

    assert main(["delete-inventory-item", "--user-access-token", "user-token-123", "--sku", "sku-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"deleted": True, "sku": "sku-1"}
    assert [call[0] for call in calls] == ["list", "get", "upsert", "upsert", "delete"]


def test_cli_offer_commands_output_json(monkeypatch, capsys, tmp_path: Path):
    payload_file = tmp_path / "offer.json"
    payload_file.write_text(
        json.dumps({"sku": "sku-1", "marketplaceId": "EBAY_US", "format": "FIXED_PRICE"}),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def get_offers_raw(self, user_access_token: str, *, sku: str, marketplace_id: str | None = None):
            calls.append(("list", user_access_token, sku, marketplace_id))
            return {"offers": [{"offerId": "offer-1", "sku": sku}]}

        def get_offer(self, offer_id: str, user_access_token: str):
            calls.append(("get", offer_id, user_access_token))
            return {"offerId": offer_id, "sku": "sku-1"}

        def create_offer_raw(self, user_access_token: str, payload: dict):
            calls.append(("create", user_access_token, payload))
            return {"offerId": "offer-1"}

        def update_offer(self, offer_id: str, user_access_token: str, payload: dict):
            calls.append(("update", offer_id, user_access_token, payload))
            return {"offerId": offer_id, "sku": payload["sku"]}

        def delete_offer(self, offer_id: str, user_access_token: str):
            calls.append(("delete", offer_id, user_access_token))

        def publish_offer(self, offer_id: str, user_access_token: str):
            calls.append(("publish", offer_id, user_access_token))
            return {"listingId": "listing-1"}

        def withdraw_offer(self, offer_id: str, user_access_token: str):
            calls.append(("withdraw", offer_id, user_access_token))
            return {"offerId": offer_id, "status": "UNPUBLISHED"}

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    assert main(["list-offers", "--user-access-token", "user-token-123", "--sku", "sku-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"offers": [{"offerId": "offer-1", "sku": "sku-1"}]}

    assert main(["get-offer", "--user-access-token", "user-token-123", "--offer-id", "offer-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"offerId": "offer-1", "sku": "sku-1"}

    assert main(
        [
            "create-offer",
            "--user-access-token",
            "user-token-123",
            "--payload-file",
            str(payload_file),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"offerId": "offer-1"}

    assert main(
        [
            "update-offer",
            "--user-access-token",
            "user-token-123",
            "--offer-id",
            "offer-1",
            "--payload-file",
            str(payload_file),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"offerId": "offer-1", "sku": "sku-1"}

    assert main(["delete-offer", "--user-access-token", "user-token-123", "--offer-id", "offer-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"deleted": True, "offer_id": "offer-1"}

    assert main(["publish-offer", "--user-access-token", "user-token-123", "--offer-id", "offer-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"listingId": "listing-1"}

    assert main(["withdraw-offer", "--user-access-token", "user-token-123", "--offer-id", "offer-1"]) == 0
    assert json.loads(capsys.readouterr().out) == {"offerId": "offer-1", "status": "UNPUBLISHED"}
    assert [call[0] for call in calls] == ["list", "get", "create", "update", "delete", "publish", "withdraw"]


def test_cli_list_fulfillment_policies_outputs_json(monkeypatch, capsys):
    class _FakePolicy:
        def __init__(self) -> None:
            self.policy_id = "policy-1"
            self.name = "Policy 1"
            self.marketplace_id = "EBAY_US"
            self.category_types = ["ALL_EXCLUDING_MOTORS_VEHICLES"]
            self.description = "Test"

    class _FakeClient:
        def get_fulfillment_policies_raw(self, user_access_token: str, *, marketplace_id: str | None = None):
            assert user_access_token == "user-token-123"
            assert marketplace_id == "EBAY_US"
            return {
                "fulfillmentPolicies": [
                    {
                        "fulfillmentPolicyId": "policy-1",
                        "name": "Policy 1",
                        "marketplaceId": "EBAY_US",
                        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                        "description": "Test",
                    }
                ]
            }

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "list-fulfillment-policies",
            "--user-access-token",
            "user-token-123",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "fulfillmentPolicies": [
            {
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "description": "Test",
                "marketplaceId": "EBAY_US",
                "name": "Policy 1",
                "fulfillmentPolicyId": "policy-1",
            }
        ]
    }


def test_cli_list_payment_policies_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_payment_policies_raw(self, user_access_token: str, *, marketplace_id: str | None = None):
            assert user_access_token == "user-token-123"
            assert marketplace_id == "EBAY_US"
            return {
                "paymentPolicies": [
                    {
                        "paymentPolicyId": "policy-1",
                        "name": "Policy 1",
                        "marketplaceId": "EBAY_US",
                    }
                ]
            }

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "list-payment-policies",
            "--user-access-token",
            "user-token-123",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "paymentPolicies": [
            {
                "marketplaceId": "EBAY_US",
                "name": "Policy 1",
                "paymentPolicyId": "policy-1",
            }
        ]
    }


def test_cli_get_payment_policy_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_payment_policy(self, policy_id: str, user_access_token: str):
            assert policy_id == "policy-1"
            assert user_access_token == "user-token-123"
            return {"paymentPolicyId": "policy-1", "name": "Policy 1"}

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "get-payment-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {"paymentPolicyId": "policy-1", "name": "Policy 1"}


def test_cli_list_return_policies_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_return_policies_raw(self, user_access_token: str, *, marketplace_id: str | None = None):
            assert user_access_token == "user-token-123"
            assert marketplace_id == "EBAY_US"
            return {
                "returnPolicies": [
                    {
                        "returnPolicyId": "policy-1",
                        "name": "Policy 1",
                        "marketplaceId": "EBAY_US",
                    }
                ]
            }

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "list-return-policies",
            "--user-access-token",
            "user-token-123",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "returnPolicies": [
            {
                "marketplaceId": "EBAY_US",
                "name": "Policy 1",
                "returnPolicyId": "policy-1",
            }
        ]
    }


def test_cli_get_return_policy_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_return_policy(self, policy_id: str, user_access_token: str):
            assert policy_id == "policy-1"
            assert user_access_token == "user-token-123"
            return {"returnPolicyId": "policy-1", "name": "Policy 1"}

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "get-return-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {"returnPolicyId": "policy-1", "name": "Policy 1"}


def test_cli_get_fulfillment_policy_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_fulfillment_policy(self, policy_id: str, user_access_token: str):
            assert policy_id == "policy-1"
            assert user_access_token == "user-token-123"
            return {"fulfillmentPolicyId": "policy-1", "name": "Policy 1"}

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "get-fulfillment-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {"fulfillmentPolicyId": "policy-1", "name": "Policy 1"}


def test_cli_create_update_delete_fulfillment_policy(monkeypatch, capsys, tmp_path: Path):
    payload_file = tmp_path / "policy.json"
    payload_file.write_text(
        json.dumps(
            {
                "name": "Policy 1",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def create_fulfillment_policy(self, user_access_token: str, payload: dict):
            calls.append(("create", user_access_token, payload))
            return {"fulfillmentPolicyId": "policy-1"}

        def update_fulfillment_policy(self, policy_id: str, user_access_token: str, payload: dict):
            calls.append(("update", policy_id, user_access_token, payload))
            return {"fulfillmentPolicyId": policy_id, "name": payload["name"]}

        def delete_fulfillment_policy(self, policy_id: str, user_access_token: str):
            calls.append(("delete", policy_id, user_access_token))

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc_create = main(
        [
            "create-fulfillment-policy",
            "--user-access-token",
            "user-token-123",
            "--payload-file",
            str(payload_file),
        ]
    )
    create_body = json.loads(capsys.readouterr().out)

    rc_update = main(
        [
            "update-fulfillment-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
            "--payload-file",
            str(payload_file),
        ]
    )
    update_body = json.loads(capsys.readouterr().out)

    rc_delete = main(
        [
            "delete-fulfillment-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
        ]
    )
    delete_body = json.loads(capsys.readouterr().out)

    assert rc_create == 0
    assert rc_update == 0
    assert rc_delete == 0
    assert create_body == {"fulfillmentPolicyId": "policy-1"}
    assert update_body == {"fulfillmentPolicyId": "policy-1", "name": "Policy 1"}
    assert delete_body == {"deleted": True, "policy_id": "policy-1"}
    assert [call[0] for call in calls] == ["create", "update", "delete"]


def test_cli_create_update_delete_return_policy(monkeypatch, capsys, tmp_path: Path):
    payload_file = tmp_path / "policy.json"
    payload_file.write_text(
        json.dumps(
            {
                "name": "Policy 1",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def create_return_policy(self, user_access_token: str, payload: dict):
            calls.append(("create", user_access_token, payload))
            return {"returnPolicyId": "policy-1"}

        def update_return_policy(self, policy_id: str, user_access_token: str, payload: dict):
            calls.append(("update", policy_id, user_access_token, payload))
            return {"returnPolicyId": policy_id, "name": payload["name"]}

        def delete_return_policy(self, policy_id: str, user_access_token: str):
            calls.append(("delete", policy_id, user_access_token))

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc_create = main(
        [
            "create-return-policy",
            "--user-access-token",
            "user-token-123",
            "--payload-file",
            str(payload_file),
        ]
    )
    create_body = json.loads(capsys.readouterr().out)

    rc_update = main(
        [
            "update-return-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
            "--payload-file",
            str(payload_file),
        ]
    )
    update_body = json.loads(capsys.readouterr().out)

    rc_delete = main(
        [
            "delete-return-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
        ]
    )
    delete_body = json.loads(capsys.readouterr().out)

    assert rc_create == 0
    assert rc_update == 0
    assert rc_delete == 0
    assert create_body == {"returnPolicyId": "policy-1"}
    assert update_body == {"returnPolicyId": "policy-1", "name": "Policy 1"}
    assert delete_body == {"deleted": True, "policy_id": "policy-1"}
    assert [call[0] for call in calls] == ["create", "update", "delete"]


def test_cli_create_update_delete_payment_policy(monkeypatch, capsys, tmp_path: Path):
    payload_file = tmp_path / "policy.json"
    payload_file.write_text(
        json.dumps(
            {
                "name": "Policy 1",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def create_payment_policy(self, user_access_token: str, payload: dict):
            calls.append(("create", user_access_token, payload))
            return {"paymentPolicyId": "policy-1"}

        def update_payment_policy(self, policy_id: str, user_access_token: str, payload: dict):
            calls.append(("update", policy_id, user_access_token, payload))
            return {"paymentPolicyId": policy_id, "name": payload["name"]}

        def delete_payment_policy(self, policy_id: str, user_access_token: str):
            calls.append(("delete", policy_id, user_access_token))

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc_create = main(
        [
            "create-payment-policy",
            "--user-access-token",
            "user-token-123",
            "--payload-file",
            str(payload_file),
        ]
    )
    create_body = json.loads(capsys.readouterr().out)

    rc_update = main(
        [
            "update-payment-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
            "--payload-file",
            str(payload_file),
        ]
    )
    update_body = json.loads(capsys.readouterr().out)

    rc_delete = main(
        [
            "delete-payment-policy",
            "--user-access-token",
            "user-token-123",
            "--policy-id",
            "policy-1",
        ]
    )
    delete_body = json.loads(capsys.readouterr().out)

    assert rc_create == 0
    assert rc_update == 0
    assert rc_delete == 0
    assert create_body == {"paymentPolicyId": "policy-1"}
    assert update_body == {"paymentPolicyId": "policy-1", "name": "Policy 1"}
    assert delete_body == {"deleted": True, "policy_id": "policy-1"}
    assert [call[0] for call in calls] == ["create", "update", "delete"]


def test_cli_get_opted_in_programs_outputs_json(monkeypatch, capsys):
    class _FakeClient:
        def get_opted_in_programs(self, user_access_token: str):
            assert user_access_token == "user-token-123"
            return [{"programType": "SELLING_POLICY_MANAGEMENT"}]

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "get-opted-in-programs",
            "--user-access-token",
            "user-token-123",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {"programs": [{"programType": "SELLING_POLICY_MANAGEMENT"}]}


def test_cli_opt_in_program_outputs_json(monkeypatch, capsys):
    calls: list[tuple[str, str]] = []

    class _FakeClient:
        def opt_in_to_program(self, user_access_token: str, program_type: str):
            calls.append((user_access_token, program_type))

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "opt-in-program",
            "--user-access-token",
            "user-token-123",
            "--program-type",
            "SELLING_POLICY_MANAGEMENT",
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "opted_in": True,
        "program_type": "SELLING_POLICY_MANAGEMENT",
    }
    assert calls == [("user-token-123", "SELLING_POLICY_MANAGEMENT")]


def test_cli_get_opted_in_programs_falls_back_to_env(monkeypatch, capsys):
    class _FakeClient:
        def get_opted_in_programs(self, user_access_token: str):
            assert user_access_token == "env-token-123"
            return [{"programType": "SELLING_POLICY_MANAGEMENT"}]

    monkeypatch.setenv("EBAY_USER_ACCESS_TOKEN", "env-token-123")
    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(["get-opted-in-programs"])

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {"programs": [{"programType": "SELLING_POLICY_MANAGEMENT"}]}


def test_cli_requires_user_access_token_when_missing(monkeypatch):
    monkeypatch.delenv("EBAY_USER_ACCESS_TOKEN", raising=False)

    try:
        main(["get-opted-in-programs"])
    except SystemExit as exc:
        assert str(exc) == (
            "user access token is required; pass --user-access-token or set EBAY_USER_ACCESS_TOKEN"
        )
    else:
        raise AssertionError("expected SystemExit")


def test_cli_create_listing_reuses_existing_client(monkeypatch, capsys):
    calls: list[tuple[str, object]] = []

    class _FakeClient:
        def create_inventory_location(self, merchant_location_key: str, user_token: str, payload: dict):
            calls.append(("create_inventory_location", merchant_location_key, user_token, payload))

        def create_or_replace_inventory_item(self, sku: str, user_token: str, payload: dict):
            calls.append(("create_or_replace_inventory_item", sku, user_token, payload))

        def create_offer(self, user_token: str, payload: dict) -> str:
            calls.append(("create_offer", user_token, payload))
            return "offer-123"

        def publish_offer(self, offer_id: str, user_token: str) -> dict:
            calls.append(("publish_offer", offer_id, user_token))
            return {"listingId": "listing-123"}

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "create-listing",
            "--user-access-token",
            "user-token-123",
            "--sku",
            "sku-1",
            "--merchant-location-key",
            "loc-1",
            "--title",
            "Test title",
            "--description",
            "Test description",
            "--category-id",
            "9355",
            "--image-url",
            "https://example.com/a.jpg",
            "--fulfillment-policy-id",
            "fulfill-1",
            "--payment-policy-id",
            "payment-1",
            "--return-policy-id",
            "return-1",
            "--price",
            "19.99",
            "--brand",
            "Codex",
            "--mpn",
            "codex-1",
            "--location-city",
            "San Jose",
            "--location-state",
            "CA",
            "--location-country",
            "US",
        ]
    )

    assert rc == 0
    assert [c[0] for c in calls] == [
        "create_inventory_location",
        "create_or_replace_inventory_item",
        "create_offer",
        "publish_offer",
    ]
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "offer_id": "offer-123",
        "publish_response": {"listingId": "listing-123"},
        "sku": "sku-1",
    }
    inventory_payload = calls[1][3]
    assert inventory_payload["product"]["aspects"] == {"Brand": ["Codex"]}


def test_cli_create_listing_supports_arbitrary_aspects(monkeypatch, capsys, tmp_path: Path):
    calls: list[tuple[str, object]] = []
    aspects_file = tmp_path / "aspects.json"
    aspects_file.write_text(
        json.dumps(
            {
                "Storage Capacity": "64 GB",
                "Color": ["Black", "Graphite"],
            }
        ),
        encoding="utf-8",
    )

    class _FakeClient:
        def create_inventory_location(self, merchant_location_key: str, user_token: str, payload: dict):
            calls.append(("create_inventory_location", merchant_location_key, user_token, payload))

        def create_or_replace_inventory_item(self, sku: str, user_token: str, payload: dict):
            calls.append(("create_or_replace_inventory_item", sku, user_token, payload))

        def create_offer(self, user_token: str, payload: dict) -> str:
            calls.append(("create_offer", user_token, payload))
            return "offer-123"

        def publish_offer(self, offer_id: str, user_token: str) -> dict:
            calls.append(("publish_offer", offer_id, user_token))
            return {"listingId": "listing-123"}

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    rc = main(
        [
            "create-listing",
            "--user-access-token",
            "user-token-123",
            "--sku",
            "sku-1",
            "--merchant-location-key",
            "loc-1",
            "--title",
            "Test title",
            "--description",
            "Test description",
            "--category-id",
            "9355",
            "--image-url",
            "https://example.com/a.jpg",
            "--fulfillment-policy-id",
            "fulfill-1",
            "--payment-policy-id",
            "payment-1",
            "--return-policy-id",
            "return-1",
            "--price",
            "19.99",
            "--brand",
            "Codex",
            "--aspect",
            "Storage Capacity=128 GB",
            "--aspect",
            "Color=Blue",
            "--aspects-file",
            str(aspects_file),
        ]
    )

    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["offer_id"] == "offer-123"
    inventory_payload = calls[0][3] if calls[0][0] == "create_or_replace_inventory_item" else calls[1][3]
    assert inventory_payload["product"]["aspects"] == {
        "Brand": ["Codex"],
        "Color": ["Black", "Graphite", "Blue"],
        "Storage Capacity": ["64 GB", "128 GB"],
    }


def test_cli_create_listing_rejects_invalid_aspect_format(monkeypatch):
    class _FakeClient:
        pass

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    with pytest.raises(SystemExit, match="aspect must use NAME=VALUE format"):
        main(
            [
                "create-listing",
                "--user-access-token",
                "user-token-123",
                "--sku",
                "sku-1",
                "--merchant-location-key",
                "loc-1",
                "--title",
                "Test title",
                "--description",
                "Test description",
                "--category-id",
                "9355",
                "--image-url",
                "https://example.com/a.jpg",
                "--fulfillment-policy-id",
                "fulfill-1",
                "--payment-policy-id",
                "payment-1",
                "--return-policy-id",
                "return-1",
                "--price",
                "19.99",
                "--aspect",
                "Storage Capacity",
            ]
        )


def test_cli_create_listing_requires_complete_location_tuple(monkeypatch):
    class _FakeClient:
        pass

    monkeypatch.setattr("pkg.ebay_cli._client_from_env", lambda marketplace_id: _FakeClient())

    try:
        main(
            [
                "create-listing",
                "--user-access-token",
                "user-token-123",
                "--sku",
                "sku-1",
                "--merchant-location-key",
                "loc-1",
                "--title",
                "Test title",
                "--description",
                "Test description",
                "--category-id",
                "9355",
                "--image-url",
                "https://example.com/a.jpg",
                "--fulfillment-policy-id",
                "fulfill-1",
                "--payment-policy-id",
                "payment-1",
                "--return-policy-id",
                "return-1",
                "--price",
                "19.99",
                "--location-city",
                "San Jose",
            ]
        )
    except SystemExit as exc:
        assert str(exc) == (
            "--location-city, --location-state, and --location-country must be provided together"
        )
    else:
        raise AssertionError("expected SystemExit")
