#!/usr/bin/env bash
# One-time setup of the *_latest views - the read surface over the
# append-only snapshot tables (newest snapshot per primary key;
# outcome_final outranks ladder_complete on timestamp ties). Safe to
# re-run any time: every statement is CREATE OR REPLACE VIEW.
#
# Run after setup-bq.sh created the tables (setup-bq.sh also invokes
# this at the end, so a fresh bootstrap needs only setup-bq.sh).
#
# Usage: PROJECT_ID=my-project [DATASET=autocloud_rollout_intel] \
#        ./setup-views.sh
set -euo pipefail

PROJECT_ID=${PROJECT_ID:?set PROJECT_ID}
DATASET=${DATASET:-autocloud_rollout_intel}
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${DIR}/generate_ddl.py" emit-views "${PROJECT_ID}" "${DATASET}" \
  | bq query --use_legacy_sql=false --project_id="${PROJECT_ID}"

echo "DONE - *_latest views ready in ${PROJECT_ID}:${DATASET}"
