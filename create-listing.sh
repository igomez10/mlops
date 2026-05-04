#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: $name" >&2
    exit 1
  fi
}

require_env "EBAY_USER_ACCESS_TOKEN"
require_env "EBAY_SANDBOX_FULFILLMENT_POLICY_ID"
require_env "EBAY_SANDBOX_PAYMENT_POLICY_ID"
require_env "EBAY_SANDBOX_RETURN_POLICY_ID"

TIMESTAMP="$(date +%s)"
SKU="${SKU:-codex-sku-$TIMESTAMP}"
MERCHANT_LOCATION_KEY="${MERCHANT_LOCATION_KEY:-codex-loc-$TIMESTAMP}"
TITLE="${TITLE:-Test listing from CLI $TIMESTAMP}"
DESCRIPTION="${DESCRIPTION:-Created from create-listing.sh}"
CATEGORY_ID="${CATEGORY_ID:-9355}"
IMAGE_URL="${IMAGE_URL:-https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg}"
FULFILLMENT_POLICY_ID="${FULFILLMENT_POLICY_ID:-$EBAY_SANDBOX_FULFILLMENT_POLICY_ID}"
PAYMENT_POLICY_ID="${PAYMENT_POLICY_ID:-$EBAY_SANDBOX_PAYMENT_POLICY_ID}"
RETURN_POLICY_ID="${RETURN_POLICY_ID:-$EBAY_SANDBOX_RETURN_POLICY_ID}"
PRICE="${PRICE:-19.99}"
CURRENCY="${CURRENCY:-USD}"
QUANTITY="${QUANTITY:-1}"
MARKETPLACE_ID="${MARKETPLACE_ID:-EBAY_US}"
FORMAT="${FORMAT:-FIXED_PRICE}"
CONDITION="${CONDITION:-NEW}"
BRAND="${BRAND:-Codex}"
MODEL="${MODEL:-Codex 64}"
MPN="${MPN:-codex-$TIMESTAMP}"
STORAGE_CAPACITY="${STORAGE_CAPACITY:-64 GB}"
COLOR="${COLOR:-Black}"
LOCATION_CITY="${LOCATION_CITY:-San Jose}"
LOCATION_STATE="${LOCATION_STATE:-CA}"
LOCATION_COUNTRY="${LOCATION_COUNTRY:-US}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

CREATE_LISTING_OUTPUT="$TMP_DIR/create-listing.json"

echo "Creating listing for SKU: $SKU"
uv run python -m pkg.ebay_cli create-listing \
  --sku "$SKU" \
  --merchant-location-key "$MERCHANT_LOCATION_KEY" \
  --title "$TITLE" \
  --description "$DESCRIPTION" \
  --category-id "$CATEGORY_ID" \
  --image-url "$IMAGE_URL" \
  --fulfillment-policy-id "$FULFILLMENT_POLICY_ID" \
  --payment-policy-id "$PAYMENT_POLICY_ID" \
  --return-policy-id "$RETURN_POLICY_ID" \
  --price "$PRICE" \
  --currency "$CURRENCY" \
  --quantity "$QUANTITY" \
  --marketplace-id "$MARKETPLACE_ID" \
  --format "$FORMAT" \
  --condition "$CONDITION" \
  --brand "$BRAND" \
  --mpn "$MPN" \
  --aspect "Storage Capacity=$STORAGE_CAPACITY" \
  --aspect "Color=$COLOR" \
  --aspect "Model=$MODEL" \
  --location-city "$LOCATION_CITY" \
  --location-state "$LOCATION_STATE" \
  --location-country "$LOCATION_COUNTRY" > "$CREATE_LISTING_OUTPUT"

OFFER_ID="$(
  python - "$CREATE_LISTING_OUTPUT" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    print(json.load(f)["offer_id"])
PY
)"

LISTING_ID="$(
  python - "$CREATE_LISTING_OUTPUT" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    print(json.load(f)["publish_response"]["listingId"])
PY
)"

echo "Listing created"
echo "SKU: $SKU"
echo "Offer ID: $OFFER_ID"
echo "Listing ID: $LISTING_ID"
echo "Sandbox URL: https://www.sandbox.ebay.com/itm/$LISTING_ID"
