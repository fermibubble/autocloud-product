#!/usr/bin/env bash
# One-time product setup against a running harness: mint the tenant token,
# then apply the bundle. Requires the ensemble CLI on PATH.
set -euo pipefail
API="${ENSEMBLE_API:-http://localhost:8088}"

if [ -z "${ENSEMBLE_TOKEN:-}" ]; then
  echo "minting autocloud-product tenant token..."
  ENSEMBLE_TOKEN=$(curl -s -X POST "$API/v1/admin/tokens" \
    -d '{"tenant":"autocloud-product","project":"default","name":"autocloud-product-admin"}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
  export ENSEMBLE_TOKEN
  echo "export ENSEMBLE_TOKEN=$ENSEMBLE_TOKEN   # save this — shown once"
fi

ensemble apply "$(dirname "$0")/.."
