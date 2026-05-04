from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from pkg.config import CloudSettings
from pkg.ebay_listing_prefill import EbayDraftPrefillService
from pkg.posts import Post


def _settings() -> CloudSettings:
    return CloudSettings(
        gcp_project_id="proj-1",
        gcs_bucket=None,
        gcs_images_bucket=None,
        firestore_database_id="(default)",
        gemini_model="gemini-test",
        vertex_location="us-central1",
        ebay_marketplace_id="EBAY_US",
    )


def _post(description: str = "Apple AirPods Pro earbuds with white charging case") -> Post:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return Post(
        id="post-1",
        name="p-post1",
        created_at=now,
        updated_at=now,
        description=description,
    )


def _analysis() -> dict:
    return {
        "product_name": "Apple AirPods Pro",
        "brand": "Apple",
        "model": "AirPods Pro",
        "category": "Earbud Headphones",
        "condition_estimate": "good",
        "visible_text": ["AirPods Pro"],
        "price_estimate": {"low": 110, "high": 150, "currency": "USD"},
    }


def test_build_draft_prefills_missing_required_aspects_with_gemini() -> None:
    ebay_client = MagicMock()
    ebay_client.get_category_suggestions.return_value = [
        SimpleNamespace(category_id="9355"),
    ]
    ebay_client.get_valid_conditions.return_value = ["NEW", "USED_EXCELLENT", "USED_GOOD"]
    ebay_client.get_item_aspects_for_category.return_value = [
        {"localizedAspectName": "Brand", "aspectConstraint": {"aspectRequired": True}},
        {"localizedAspectName": "Model", "aspectConstraint": {"aspectRequired": True}},
        {
            "localizedAspectName": "Color",
            "aspectConstraint": {"aspectRequired": True},
            "aspectValues": [{"localizedValue": "White"}, {"localizedValue": "Black"}],
        },
        {
            "localizedAspectName": "Connectivity",
            "aspectConstraint": {"aspectRequired": True},
            "aspectValues": [{"localizedValue": "Bluetooth"}, {"localizedValue": "Wired"}],
        },
    ]

    gemini_client = MagicMock()
    gemini_client.generate_text.return_value = (
        '{"Color": ["White"], "Connectivity": ["Bluetooth"], "Brand": ["Should Not Win"]}'
    )

    service = EbayDraftPrefillService(
        settings=_settings(),
        ebay_client=ebay_client,
        gemini_client_factory=lambda _: gemini_client,
    )

    draft = service.build_draft(
        post=_post(description="Apple AirPods Pro earbuds with charging case"),
        analysis=_analysis(),
        user_id="user-123",
    )

    assert draft["category_id"] == "9355"
    assert draft["condition"] == "USED_GOOD"
    assert draft["price"] == 130.0
    assert draft["item_specifics"] == {
        "Brand": ["Apple"],
        "Model": ["AirPods Pro"],
        "Color": ["White"],
        "Connectivity": ["Bluetooth"],
    }
    prompt = gemini_client.generate_text.call_args.args[0]
    assert "Initial description: Apple AirPods Pro earbuds with charging case" in prompt
    assert 'Missing required eBay fields:\n- "Color": allowed: White, Black' in prompt


def test_build_draft_falls_back_to_blank_values_when_gemini_fails() -> None:
    ebay_client = MagicMock()
    ebay_client.get_category_suggestions.return_value = [SimpleNamespace(category_id="9355")]
    ebay_client.get_valid_conditions.return_value = ["USED_GOOD"]
    ebay_client.get_item_aspects_for_category.return_value = [
        {"localizedAspectName": "Brand", "aspectConstraint": {"aspectRequired": True}},
        {"localizedAspectName": "Color", "aspectConstraint": {"aspectRequired": True}},
    ]

    service = EbayDraftPrefillService(
        settings=_settings(),
        ebay_client=ebay_client,
        gemini_client_factory=lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    draft = service.build_draft(post=_post(), analysis=_analysis(), user_id="user-123")

    assert draft["item_specifics"] == {
        "Brand": ["Apple"],
        "Model": ["AirPods Pro"],
        "Color": [""],
    }


def test_parse_item_specifics_response_handles_code_fence() -> None:
    raw = '```json\n{"Color":["White"]}\n```'

    parsed = EbayDraftPrefillService._parse_item_specifics_response(raw)

    assert parsed == {"Color": ["White"]}
