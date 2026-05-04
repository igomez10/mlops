from __future__ import annotations

import argparse
import json
import os
from typing import Any

import argcomplete

from pkg.config import CloudSettings
from pkg.ebay import EbayClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ebay-cli",
        description="Interact with the eBay Inventory API using existing app credentials and a user access token.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list-listings",
        help="List all eBay offers/listings visible through the seller's Inventory API token.",
    )
    list_parser.add_argument("--user-access-token")
    list_parser.add_argument("--marketplace-id", default="EBAY_US")
    list_parser.add_argument("--page-size", type=int, default=200)
    list_parser.set_defaults(func=_cmd_list_listings)

    list_inventory_parser = subparsers.add_parser(
        "list-inventory-items",
        help="List seller inventory item records.",
    )
    list_inventory_parser.add_argument("--user-access-token")
    list_inventory_parser.add_argument("--page-size", type=int, default=200)
    list_inventory_parser.add_argument("--offset", type=int, default=0)
    list_inventory_parser.set_defaults(func=_cmd_list_inventory_items)

    get_inventory_parser = subparsers.add_parser(
        "get-inventory-item",
        help="Get one inventory item by SKU.",
    )
    get_inventory_parser.add_argument("--user-access-token")
    get_inventory_parser.add_argument("--sku", required=True)
    get_inventory_parser.set_defaults(func=_cmd_get_inventory_item)

    create_inventory_parser = subparsers.add_parser(
        "create-inventory-item",
        help="Create or replace an inventory item from a JSON payload file.",
    )
    create_inventory_parser.add_argument("--user-access-token")
    create_inventory_parser.add_argument("--sku", required=True)
    create_inventory_parser.add_argument("--payload-file", required=True)
    create_inventory_parser.set_defaults(func=_cmd_create_inventory_item)

    update_inventory_parser = subparsers.add_parser(
        "update-inventory-item",
        help="Update an inventory item from a JSON payload file using createOrReplaceInventoryItem semantics.",
    )
    update_inventory_parser.add_argument("--user-access-token")
    update_inventory_parser.add_argument("--sku", required=True)
    update_inventory_parser.add_argument("--payload-file", required=True)
    update_inventory_parser.set_defaults(func=_cmd_update_inventory_item)

    delete_inventory_parser = subparsers.add_parser(
        "delete-inventory-item",
        help="Delete an inventory item by SKU.",
    )
    delete_inventory_parser.add_argument("--user-access-token")
    delete_inventory_parser.add_argument("--sku", required=True)
    delete_inventory_parser.set_defaults(func=_cmd_delete_inventory_item)

    list_offers_parser = subparsers.add_parser(
        "list-offers",
        help="List offers for a seller SKU.",
    )
    list_offers_parser.add_argument("--user-access-token")
    list_offers_parser.add_argument("--sku", required=True)
    list_offers_parser.add_argument("--marketplace-id", default="EBAY_US")
    list_offers_parser.set_defaults(func=_cmd_list_offers)

    get_offer_parser = subparsers.add_parser(
        "get-offer",
        help="Get one offer by offer ID.",
    )
    get_offer_parser.add_argument("--user-access-token")
    get_offer_parser.add_argument("--offer-id", required=True)
    get_offer_parser.set_defaults(func=_cmd_get_offer)

    create_offer_parser = subparsers.add_parser(
        "create-offer",
        help="Create an offer from a JSON payload file.",
    )
    create_offer_parser.add_argument("--user-access-token")
    create_offer_parser.add_argument("--payload-file", required=True)
    create_offer_parser.set_defaults(func=_cmd_create_offer)

    update_offer_parser = subparsers.add_parser(
        "update-offer",
        help="Update an offer from a JSON payload file.",
    )
    update_offer_parser.add_argument("--user-access-token")
    update_offer_parser.add_argument("--offer-id", required=True)
    update_offer_parser.add_argument("--payload-file", required=True)
    update_offer_parser.set_defaults(func=_cmd_update_offer)

    delete_offer_parser = subparsers.add_parser(
        "delete-offer",
        help="Delete an offer by offer ID.",
    )
    delete_offer_parser.add_argument("--user-access-token")
    delete_offer_parser.add_argument("--offer-id", required=True)
    delete_offer_parser.set_defaults(func=_cmd_delete_offer)

    publish_offer_parser = subparsers.add_parser(
        "publish-offer",
        help="Publish an offer by offer ID.",
    )
    publish_offer_parser.add_argument("--user-access-token")
    publish_offer_parser.add_argument("--offer-id", required=True)
    publish_offer_parser.set_defaults(func=_cmd_publish_offer)

    withdraw_offer_parser = subparsers.add_parser(
        "withdraw-offer",
        help="Withdraw a published offer by offer ID.",
    )
    withdraw_offer_parser.add_argument("--user-access-token")
    withdraw_offer_parser.add_argument("--offer-id", required=True)
    withdraw_offer_parser.set_defaults(func=_cmd_withdraw_offer)

    list_fulfillment_parser = subparsers.add_parser(
        "list-fulfillment-policies",
        help="List fulfillment policies for the seller account.",
    )
    list_fulfillment_parser.add_argument("--user-access-token")
    list_fulfillment_parser.add_argument("--marketplace-id", default="EBAY_US")
    list_fulfillment_parser.set_defaults(func=_cmd_list_fulfillment_policies)

    get_fulfillment_parser = subparsers.add_parser(
        "get-fulfillment-policy",
        help="Get one fulfillment policy by ID.",
    )
    get_fulfillment_parser.add_argument("--user-access-token")
    get_fulfillment_parser.add_argument("--policy-id", required=True)
    get_fulfillment_parser.add_argument("--marketplace-id", default="EBAY_US")
    get_fulfillment_parser.set_defaults(func=_cmd_get_fulfillment_policy)

    create_fulfillment_parser = subparsers.add_parser(
        "create-fulfillment-policy",
        help="Create a fulfillment policy from a JSON payload file.",
    )
    create_fulfillment_parser.add_argument("--user-access-token")
    create_fulfillment_parser.add_argument("--payload-file", required=True)
    create_fulfillment_parser.add_argument("--marketplace-id", default="EBAY_US")
    create_fulfillment_parser.set_defaults(func=_cmd_create_fulfillment_policy)

    update_fulfillment_parser = subparsers.add_parser(
        "update-fulfillment-policy",
        help="Update a fulfillment policy from a JSON payload file.",
    )
    update_fulfillment_parser.add_argument("--user-access-token")
    update_fulfillment_parser.add_argument("--policy-id", required=True)
    update_fulfillment_parser.add_argument("--payload-file", required=True)
    update_fulfillment_parser.add_argument("--marketplace-id", default="EBAY_US")
    update_fulfillment_parser.set_defaults(func=_cmd_update_fulfillment_policy)

    delete_fulfillment_parser = subparsers.add_parser(
        "delete-fulfillment-policy",
        help="Delete a fulfillment policy by ID.",
    )
    delete_fulfillment_parser.add_argument("--user-access-token")
    delete_fulfillment_parser.add_argument("--policy-id", required=True)
    delete_fulfillment_parser.add_argument("--marketplace-id", default="EBAY_US")
    delete_fulfillment_parser.set_defaults(func=_cmd_delete_fulfillment_policy)

    list_payment_parser = subparsers.add_parser(
        "list-payment-policies",
        help="List payment policies for the seller account.",
    )
    list_payment_parser.add_argument("--user-access-token")
    list_payment_parser.add_argument("--marketplace-id", default="EBAY_US")
    list_payment_parser.set_defaults(func=_cmd_list_payment_policies)

    get_payment_parser = subparsers.add_parser(
        "get-payment-policy",
        help="Get one payment policy by ID.",
    )
    get_payment_parser.add_argument("--user-access-token")
    get_payment_parser.add_argument("--policy-id", required=True)
    get_payment_parser.add_argument("--marketplace-id", default="EBAY_US")
    get_payment_parser.set_defaults(func=_cmd_get_payment_policy)

    create_payment_parser = subparsers.add_parser(
        "create-payment-policy",
        help="Create a payment policy from a JSON payload file.",
    )
    create_payment_parser.add_argument("--user-access-token")
    create_payment_parser.add_argument("--payload-file", required=True)
    create_payment_parser.add_argument("--marketplace-id", default="EBAY_US")
    create_payment_parser.set_defaults(func=_cmd_create_payment_policy)

    update_payment_parser = subparsers.add_parser(
        "update-payment-policy",
        help="Update a payment policy from a JSON payload file.",
    )
    update_payment_parser.add_argument("--user-access-token")
    update_payment_parser.add_argument("--policy-id", required=True)
    update_payment_parser.add_argument("--payload-file", required=True)
    update_payment_parser.add_argument("--marketplace-id", default="EBAY_US")
    update_payment_parser.set_defaults(func=_cmd_update_payment_policy)

    delete_payment_parser = subparsers.add_parser(
        "delete-payment-policy",
        help="Delete a payment policy by ID.",
    )
    delete_payment_parser.add_argument("--user-access-token")
    delete_payment_parser.add_argument("--policy-id", required=True)
    delete_payment_parser.add_argument("--marketplace-id", default="EBAY_US")
    delete_payment_parser.set_defaults(func=_cmd_delete_payment_policy)

    list_return_parser = subparsers.add_parser(
        "list-return-policies",
        help="List return policies for the seller account.",
    )
    list_return_parser.add_argument("--user-access-token")
    list_return_parser.add_argument("--marketplace-id", default="EBAY_US")
    list_return_parser.set_defaults(func=_cmd_list_return_policies)

    get_return_parser = subparsers.add_parser(
        "get-return-policy",
        help="Get one return policy by ID.",
    )
    get_return_parser.add_argument("--user-access-token")
    get_return_parser.add_argument("--policy-id", required=True)
    get_return_parser.add_argument("--marketplace-id", default="EBAY_US")
    get_return_parser.set_defaults(func=_cmd_get_return_policy)

    create_return_parser = subparsers.add_parser(
        "create-return-policy",
        help="Create a return policy from a JSON payload file.",
    )
    create_return_parser.add_argument("--user-access-token")
    create_return_parser.add_argument("--payload-file", required=True)
    create_return_parser.add_argument("--marketplace-id", default="EBAY_US")
    create_return_parser.set_defaults(func=_cmd_create_return_policy)

    update_return_parser = subparsers.add_parser(
        "update-return-policy",
        help="Update a return policy from a JSON payload file.",
    )
    update_return_parser.add_argument("--user-access-token")
    update_return_parser.add_argument("--policy-id", required=True)
    update_return_parser.add_argument("--payload-file", required=True)
    update_return_parser.add_argument("--marketplace-id", default="EBAY_US")
    update_return_parser.set_defaults(func=_cmd_update_return_policy)

    delete_return_parser = subparsers.add_parser(
        "delete-return-policy",
        help="Delete a return policy by ID.",
    )
    delete_return_parser.add_argument("--user-access-token")
    delete_return_parser.add_argument("--policy-id", required=True)
    delete_return_parser.add_argument("--marketplace-id", default="EBAY_US")
    delete_return_parser.set_defaults(func=_cmd_delete_return_policy)

    list_programs_parser = subparsers.add_parser(
        "get-opted-in-programs",
        help="List seller programs the account is currently opted into.",
    )
    list_programs_parser.add_argument("--user-access-token")
    list_programs_parser.add_argument("--marketplace-id", default="EBAY_US")
    list_programs_parser.set_defaults(func=_cmd_get_opted_in_programs)

    opt_in_program_parser = subparsers.add_parser(
        "opt-in-program",
        help="Opt the seller account into an eBay seller program.",
    )
    opt_in_program_parser.add_argument("--user-access-token")
    opt_in_program_parser.add_argument("--program-type", required=True)
    opt_in_program_parser.add_argument("--marketplace-id", default="EBAY_US")
    opt_in_program_parser.set_defaults(func=_cmd_opt_in_program)

    categories_parser = subparsers.add_parser(
        "suggest-categories",
        help="Get candidate eBay category IDs for a query using the Taxonomy API.",
    )
    categories_parser.add_argument("--query", required=True)
    categories_parser.add_argument("--marketplace-id", default="EBAY_US")
    categories_parser.add_argument("--accept-language")
    categories_parser.set_defaults(func=_cmd_suggest_categories)

    shipping_services_parser = subparsers.add_parser(
        "list-shipping-services",
        help="List valid shipping service codes for a marketplace.",
    )
    shipping_services_parser.add_argument("--marketplace-id", default="EBAY_US")
    shipping_services_parser.set_defaults(func=_cmd_list_shipping_services)

    create_parser = subparsers.add_parser(
        "create-listing",
        help="Create and publish an eBay listing using the Inventory API.",
    )
    create_parser.add_argument("--user-access-token")
    create_parser.add_argument("--sku", required=True)
    create_parser.add_argument("--merchant-location-key", required=True)
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--description", required=True)
    create_parser.add_argument("--category-id", required=True)
    create_parser.add_argument("--image-url", action="append", required=True)
    create_parser.add_argument("--fulfillment-policy-id", required=True)
    create_parser.add_argument("--payment-policy-id", required=True)
    create_parser.add_argument("--return-policy-id", required=True)
    create_parser.add_argument("--price", required=True, type=float)
    create_parser.add_argument("--currency", default="USD")
    create_parser.add_argument("--quantity", type=int, default=1)
    create_parser.add_argument("--marketplace-id", default="EBAY_US")
    create_parser.add_argument("--format", default="FIXED_PRICE")
    create_parser.add_argument("--condition", default="NEW")
    create_parser.add_argument("--brand")
    create_parser.add_argument("--mpn")
    create_parser.add_argument(
        "--aspect",
        action="append",
        default=[],
        help="Add an item aspect using NAME=VALUE. Repeat for multiple aspects or values.",
    )
    create_parser.add_argument(
        "--aspects-file",
        help="Path to a JSON object of item aspects where values are strings or arrays of strings.",
    )
    create_parser.add_argument("--location-city")
    create_parser.add_argument("--location-state")
    create_parser.add_argument("--location-country")
    create_parser.set_defaults(func=_cmd_create_listing)

    return parser


def _client_from_env(*, marketplace_id: str) -> EbayClient:
    settings = CloudSettings.from_env()
    client = EbayClient.from_settings(settings)
    client._marketplace_id = marketplace_id
    return client


def _load_json_file(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit("payload file must contain a JSON object")
    return data


def _load_aspects_file(path: str) -> dict[str, list[str]]:
    data = _load_json_file(path)
    aspects: dict[str, list[str]] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not key:
            raise SystemExit("aspect keys must be non-empty strings")
        if isinstance(value, str):
            aspects[key] = [value]
            continue
        if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
            aspects[key] = list(value)
            continue
        raise SystemExit("aspects file values must be strings or arrays of non-empty strings")
    return aspects


def _resolve_user_access_token(value: str | None) -> str:
    token = value or os.environ.get("EBAY_USER_ACCESS_TOKEN")
    if token:
        return token
    raise SystemExit("user access token is required; pass --user-access-token or set EBAY_USER_ACCESS_TOKEN")


def _parse_aspect_flag(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise SystemExit("aspect must use NAME=VALUE format")
    name, raw_value = value.split("=", 1)
    name = name.strip()
    raw_value = raw_value.strip()
    if not name or not raw_value:
        raise SystemExit("aspect must use NAME=VALUE format")
    return name, raw_value


def _resolve_aspects(
    *,
    brand: str | None,
    aspect_flags: list[str] | None,
    aspects_file: str | None,
) -> dict[str, list[str]]:
    aspects: dict[str, list[str]] = {}
    if brand:
        aspects["Brand"] = [brand]
    if aspects_file:
        for key, values in _load_aspects_file(aspects_file).items():
            aspects[key] = list(values)
    for item in aspect_flags or []:
        key, value = _parse_aspect_flag(item)
        aspects.setdefault(key, []).append(value)
    return aspects


def _list_all_offers(
    client: EbayClient,
    *,
    user_access_token: str,
    page_size: int,
) -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = client.get_inventory_items_raw(
            user_access_token,
            limit=page_size,
            offset=offset,
        )
        inventory_items = list(page.get("inventoryItems") or [])
        skus = [str(raw.get("sku") or "") for raw in inventory_items if str(raw.get("sku") or "")]
        next_url = str(page.get("next")) if page.get("next") else None
        for sku in skus:
            offers_body = client.get_offers_raw(user_access_token, sku=sku)
            listings.extend(list(offers_body.get("offers") or []))
        if not next_url or len(skus) < page_size:
            break
        offset += len(skus)
    return listings


def _cmd_list_listings(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = {
        "listings": _list_all_offers(
            client,
            user_access_token=user_access_token,
            page_size=args.page_size,
        )
    }
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_list_inventory_items(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.get_inventory_items_raw(
        user_access_token,
        limit=args.page_size,
        offset=args.offset,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_get_inventory_item(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.get_inventory_item(args.sku, user_access_token)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_create_inventory_item(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    client.create_or_replace_inventory_item(
        args.sku,
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps({"created": True, "sku": args.sku}, indent=2, sort_keys=True))
    return 0


def _cmd_update_inventory_item(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    client.create_or_replace_inventory_item(
        args.sku,
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps({"updated": True, "sku": args.sku}, indent=2, sort_keys=True))
    return 0


def _cmd_delete_inventory_item(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    client.delete_inventory_item(args.sku, user_access_token)
    print(json.dumps({"deleted": True, "sku": args.sku}, indent=2, sort_keys=True))
    return 0


def _cmd_list_offers(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_offers_raw(
        user_access_token,
        sku=args.sku,
        marketplace_id=args.marketplace_id,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_get_offer(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.get_offer(args.offer_id, user_access_token)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_create_offer(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.create_offer_raw(
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_update_offer(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.update_offer(
        args.offer_id,
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_delete_offer(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    client.delete_offer(args.offer_id, user_access_token)
    print(json.dumps({"deleted": True, "offer_id": args.offer_id}, indent=2, sort_keys=True))
    return 0


def _cmd_publish_offer(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.publish_offer(args.offer_id, user_access_token)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_withdraw_offer(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id="EBAY_US")
    body = client.withdraw_offer(args.offer_id, user_access_token)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_list_fulfillment_policies(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_fulfillment_policies_raw(
        user_access_token,
        marketplace_id=args.marketplace_id,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_get_fulfillment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_fulfillment_policy(
        args.policy_id,
        user_access_token,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_create_fulfillment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.create_fulfillment_policy(
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_update_fulfillment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.update_fulfillment_policy(
        args.policy_id,
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_delete_fulfillment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    client.delete_fulfillment_policy(
        args.policy_id,
        user_access_token,
    )
    body = {"deleted": True, "policy_id": args.policy_id}
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_list_payment_policies(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_payment_policies_raw(
        user_access_token,
        marketplace_id=args.marketplace_id,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_get_payment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_payment_policy(
        args.policy_id,
        user_access_token,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_create_payment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.create_payment_policy(
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_update_payment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.update_payment_policy(
        args.policy_id,
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_delete_payment_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    client.delete_payment_policy(
        args.policy_id,
        user_access_token,
    )
    body = {"deleted": True, "policy_id": args.policy_id}
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_list_return_policies(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_return_policies_raw(
        user_access_token,
        marketplace_id=args.marketplace_id,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_get_return_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_return_policy(
        args.policy_id,
        user_access_token,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_create_return_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.create_return_policy(
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_update_return_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.update_return_policy(
        args.policy_id,
        user_access_token,
        _load_json_file(args.payload_file),
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_delete_return_policy(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    client.delete_return_policy(
        args.policy_id,
        user_access_token,
    )
    body = {"deleted": True, "policy_id": args.policy_id}
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_get_opted_in_programs(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = {"programs": client.get_opted_in_programs(user_access_token)}
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_opt_in_program(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    client.opt_in_to_program(
        user_access_token,
        args.program_type,
    )
    body = {"opted_in": True, "program_type": args.program_type}
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_suggest_categories(args: argparse.Namespace) -> int:
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_category_suggestions_raw(
        args.query,
        marketplace_id=args.marketplace_id,
        accept_language=args.accept_language,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_list_shipping_services(args: argparse.Namespace) -> int:
    client = _client_from_env(marketplace_id=args.marketplace_id)
    body = client.get_shipping_services_raw(
        marketplace_id=args.marketplace_id,
    )
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def _cmd_create_listing(args: argparse.Namespace) -> int:
    user_access_token = _resolve_user_access_token(args.user_access_token)
    client = _client_from_env(marketplace_id=args.marketplace_id)
    if any(value is not None for value in (args.location_city, args.location_state, args.location_country)):
        if not all((args.location_city, args.location_state, args.location_country)):
            raise SystemExit("--location-city, --location-state, and --location-country must be provided together")
        client.create_inventory_location(
            args.merchant_location_key,
            user_access_token,
            {
                "name": args.merchant_location_key,
                "merchantLocationStatus": "ENABLED",
                "locationTypes": ["WAREHOUSE"],
                "location": {
                    "address": {
                        "city": args.location_city,
                        "stateOrProvince": args.location_state,
                        "country": args.location_country,
                    }
                },
            },
        )

    product: dict[str, Any] = {
        "title": args.title,
        "description": args.description,
        "imageUrls": list(args.image_url),
    }
    aspects = _resolve_aspects(
        brand=args.brand,
        aspect_flags=args.aspect,
        aspects_file=args.aspects_file,
    )
    if args.brand:
        product["brand"] = args.brand
    if args.mpn:
        product["mpn"] = args.mpn
    if aspects:
        product["aspects"] = aspects

    client.create_or_replace_inventory_item(
        args.sku,
        user_access_token,
        {
            "availability": {"shipToLocationAvailability": {"quantity": args.quantity}},
            "condition": args.condition,
            "product": product,
        },
    )

    offer_id = client.create_offer(
        user_access_token,
        {
            "sku": args.sku,
            "marketplaceId": args.marketplace_id,
            "format": args.format,
            "availableQuantity": args.quantity,
            "categoryId": args.category_id,
            "merchantLocationKey": args.merchant_location_key,
            "pricingSummary": {"price": {"value": f"{args.price:.2f}", "currency": args.currency}},
            "listingDescription": args.description,
            "listingPolicies": {
                "fulfillmentPolicyId": args.fulfillment_policy_id,
                "paymentPolicyId": args.payment_policy_id,
                "returnPolicyId": args.return_policy_id,
            },
        },
    )
    publish_body = client.publish_offer(offer_id, user_access_token)
    body = {
        "sku": args.sku,
        "offer_id": offer_id,
        "publish_response": publish_body,
    }
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
