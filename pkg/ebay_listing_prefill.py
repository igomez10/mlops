from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from pkg.config import CloudSettings
from pkg.ebay import EbayClient
from pkg.gemini import GeminiClient
from pkg.posts import Post

log = logging.getLogger(__name__)


@dataclass(slots=True)
class EbayDraftPrefillService:
    """Build a best-effort eBay draft from product analysis + eBay metadata."""

    settings: CloudSettings
    ebay_client: EbayClient
    gemini_client_factory: Callable[[CloudSettings], GeminiClient] = GeminiClient.from_settings

    def build_draft(
        self,
        *,
        post: Post,
        analysis: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        title = self._resolve_listing_title(analysis, fallback=post.description or post.name)
        description = self._resolve_listing_description(analysis, fallback=post.description)
        price_value, currency = self._resolve_price_and_currency(analysis)
        category_id = self._resolve_category_id(analysis, post.description)
        desired_condition = self._resolve_condition(analysis)
        valid_conditions = self.ebay_client.get_valid_conditions(
            category_id,
            marketplace_id=self.settings.ebay_marketplace_id,
        )
        condition = self._pick_condition(desired_condition, valid_conditions)
        aspects = self.ebay_client.get_item_aspects_for_category(category_id)
        required_aspects = [a for a in aspects if (a.get("aspectConstraint") or {}).get("aspectRequired")]
        item_specifics = self._build_item_specifics(
            analysis=analysis,
            required_aspects=required_aspects,
            product_description=post.description,
        )
        return {
            "user_id": user_id,
            "category_id": category_id,
            "title": title,
            "description": description,
            "condition": condition,
            "price": price_value,
            "currency": currency,
            "item_specifics": item_specifics,
        }

    def _resolve_category_id(self, analysis: dict[str, Any], fallback: str) -> str:
        query = str(analysis.get("product_name") or "").strip() or fallback
        suggestions = self.ebay_client.get_category_suggestions(
            query,
            marketplace_id=self.settings.ebay_marketplace_id,
        )
        if not suggestions:
            raise RuntimeError(f"no eBay category suggestions returned for query {query!r}")
        return suggestions[0].category_id

    @staticmethod
    def _resolve_listing_title(analysis: dict[str, Any], fallback: str) -> str:
        parts = [
            str(analysis.get("brand") or "").strip(),
            str(analysis.get("product_name") or "").strip(),
            str(analysis.get("model") or "").strip(),
        ]
        raw = " ".join(part for part in parts if part)
        title = raw or fallback.strip() or "Marketplace listing"
        return title[:80]

    @staticmethod
    def _resolve_listing_description(analysis: dict[str, Any], fallback: str) -> str:
        lines: list[str] = []
        if fallback.strip():
            lines.append(fallback.strip())
        product_name = str(analysis.get("product_name") or "").strip()
        if product_name:
            lines.append(f"Product: {product_name}")
        category = str(analysis.get("category") or "").strip()
        if category:
            lines.append(f"Category: {category}")
        condition = str(analysis.get("condition_estimate") or "").strip()
        if condition:
            lines.append(f"Condition estimate: {condition}")
        visible_text = [str(item).strip() for item in (analysis.get("visible_text") or []) if str(item).strip()]
        if visible_text:
            lines.append(f"Visible text: {', '.join(visible_text[:5])}")
        return "\n".join(lines) or "Listing created from uploaded product image."

    @staticmethod
    def _resolve_price_and_currency(analysis: dict[str, Any]) -> tuple[float, str]:
        raw_price = analysis.get("price_estimate") or {}
        if isinstance(raw_price, dict):
            low = raw_price.get("low")
            high = raw_price.get("high")
            currency = str(raw_price.get("currency") or "USD").strip() or "USD"
            low_num = float(low) if isinstance(low, (int, float)) and low > 0 else 0.0
            high_num = float(high) if isinstance(high, (int, float)) and high > 0 else 0.0
            if low_num > 0 and high_num > 0:
                return round((low_num + high_num) / 2.0, 2), currency
            if high_num > 0:
                return round(high_num, 2), currency
            if low_num > 0:
                return round(low_num, 2), currency
        return 19.99, "USD"

    @staticmethod
    def _resolve_condition(analysis: dict[str, Any]) -> str:
        normalized = str(analysis.get("condition_estimate") or "").strip().lower()
        mapping = {
            "new": "NEW",
            "like new": "USED_EXCELLENT",
            "excellent": "USED_EXCELLENT",
            "very good": "USED_VERY_GOOD",
            "good": "USED_GOOD",
            "fair": "USED_ACCEPTABLE",
            "used": "USED_GOOD",
        }
        return mapping.get(normalized, "USED_GOOD")

    @staticmethod
    def _pick_condition(desired: str, valid_conditions: list[str]) -> str:
        if not valid_conditions:
            return desired
        valid = set(valid_conditions)
        if desired in valid:
            return desired
        order = [
            "FOR_PARTS_OR_NOT_WORKING",
            "USED_ACCEPTABLE",
            "USED_GOOD",
            "USED_VERY_GOOD",
            "USED_EXCELLENT",
            "SELLER_REFURBISHED",
            "GOOD_REFURBISHED",
            "VERY_GOOD_REFURBISHED",
            "EXCELLENT_REFURBISHED",
            "CERTIFIED_REFURBISHED",
            "NEW_WITH_DEFECTS",
            "NEW_OTHER",
            "LIKE_NEW",
            "NEW",
        ]
        try:
            idx = order.index(desired)
        except ValueError:
            return valid_conditions[0]
        for cond in order[idx + 1 :]:
            if cond in valid:
                return cond
        for cond in reversed(order[:idx]):
            if cond in valid:
                return cond
        return valid_conditions[0]

    def _build_item_specifics(
        self,
        *,
        analysis: dict[str, Any],
        required_aspects: list[dict[str, Any]],
        product_description: str,
    ) -> dict[str, list[str]]:
        base_specifics = self._build_known_item_specifics(
            analysis=analysis,
            required_aspects=required_aspects,
            product_description=product_description,
        )
        missing_aspects = [
            aspect
            for aspect in required_aspects
            if str(aspect.get("localizedAspectName") or "").strip() not in base_specifics
        ]
        if not missing_aspects:
            return base_specifics
        try:
            gemini_client = self.gemini_client_factory(self.settings)
            gemini_specifics = self._suggest_missing_item_specifics(
                analysis=analysis,
                product_description=product_description,
                aspects=missing_aspects,
                gemini_client=gemini_client,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Gemini item-specifics inference failed: %s", exc)
            gemini_specifics = {
                str(a.get("localizedAspectName") or ""): [""]
                for a in missing_aspects
                if str(a.get("localizedAspectName") or "").strip()
            }
        return {**base_specifics, **gemini_specifics}

    @staticmethod
    def _build_known_item_specifics(
        *,
        analysis: dict[str, Any],
        required_aspects: list[dict[str, Any]],
        product_description: str,
    ) -> dict[str, list[str]]:
        specifics: dict[str, list[str]] = {}
        brand = str(analysis.get("brand") or "").strip()
        model = str(analysis.get("model") or "").strip()
        product_name = str(analysis.get("product_name") or "").strip()
        if brand:
            specifics["Brand"] = [brand]
        if model:
            specifics["Model"] = [model]
        searchable_text = " ".join(
            part
            for part in [
                product_description.strip(),
                product_name,
                brand,
                model,
                str(analysis.get("category") or "").strip(),
                str(analysis.get("condition_estimate") or "").strip(),
                " ".join(str(item).strip() for item in (analysis.get("visible_text") or []) if str(item).strip()),
            ]
            if part
        ).lower()
        for aspect in required_aspects:
            aspect_name = str(aspect.get("localizedAspectName") or "").strip()
            if not aspect_name:
                continue
            normalized = aspect_name.strip().lower()
            value = {
                "brand": brand,
                "model": model,
                "product name": product_name,
            }.get(normalized)
            if value:
                specifics[aspect_name] = [value]
                continue
            allowed_values = [
                str(raw.get("localizedValue") or "").strip()
                for raw in (aspect.get("aspectValues") or [])
                if str(raw.get("localizedValue") or "").strip()
            ]
            matched_allowed = next((allowed for allowed in allowed_values if allowed.lower() in searchable_text), None)
            if matched_allowed:
                specifics[aspect_name] = [matched_allowed]
        return specifics

    @staticmethod
    def _suggest_missing_item_specifics(
        *,
        analysis: dict[str, Any],
        product_description: str,
        aspects: list[dict[str, Any]],
        gemini_client: GeminiClient,
    ) -> dict[str, list[str]]:
        names_with_values: list[tuple[str, list[str]]] = []
        for aspect in aspects:
            name = str(aspect.get("localizedAspectName") or "").strip()
            if not name:
                continue
            allowed = [
                str(v.get("localizedValue") or "")
                for v in (aspect.get("aspectValues") or [])
                if str(v.get("localizedValue") or "").strip()
            ]
            names_with_values.append((name, allowed[:15]))
        if not names_with_values:
            return {}
        product_info = "\n".join(
            f"{k}: {v}"
            for k, v in [
                ("Initial description", product_description.strip()),
                ("Product", str(analysis.get("product_name") or "").strip()),
                ("Brand", str(analysis.get("brand") or "").strip()),
                ("Model", str(analysis.get("model") or "").strip()),
                ("High-level category", str(analysis.get("category") or "").strip()),
                ("Condition", str(analysis.get("condition_estimate") or "").strip()),
                ("Visible text", ", ".join(str(item).strip() for item in (analysis.get("visible_text") or []))),
            ]
            if v
        )
        aspects_spec = "\n".join(
            f'- "{name}": {("allowed: " + ", ".join(values)) if values else "(any string)"}'
            for name, values in names_with_values
        )
        prompt = (
            "You are filling missing required eBay product fields for a listing.\n\n"
            "Use the product description and analysis below to make a best-effort guess.\n"
            "Only populate fields you can infer. If uncertain, return an empty string for that field.\n"
            "When allowed values are provided, pick exactly one of those values.\n\n"
            f"Known product information:\n{product_info}\n\n"
            f"Missing required eBay fields:\n{aspects_spec}\n\n"
            "Return ONLY valid JSON. Keys must exactly match the field names above. "
            'Each value must be a single-element array, for example {"Color": ["White"]}.'
        )
        raw = gemini_client.generate_text(prompt)
        parsed = EbayDraftPrefillService._parse_item_specifics_response(raw)
        if not parsed:
            return {name: [""] for name, _ in names_with_values}
        result: dict[str, list[str]] = {}
        for name, _ in names_with_values:
            value = parsed.get(name)
            if value is None:
                result[name] = [""]
                continue
            if isinstance(value, list):
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                result[name] = [cleaned[0]] if cleaned else [""]
                continue
            if isinstance(value, str):
                result[name] = [value.strip()] if value.strip() else [""]
                continue
            result[name] = [""]
        return result

    @staticmethod
    def _parse_item_specifics_response(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if not text:
            return {}
        # Prefer an explicit fenced code block when present.
        code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_match:
            try:
                data = json.loads(code_match.group(1))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        # Scan from every `{` position so we find the first valid JSON object
        # regardless of surrounding text or multiple brace pairs in the response.
        decoder = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                data, _ = decoder.raw_decode(text, i)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
        return {}
