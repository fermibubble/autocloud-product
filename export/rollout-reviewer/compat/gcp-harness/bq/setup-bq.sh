#!/usr/bin/env bash
# One-time (and per-schema-change) DDL for the rollout-intel BigQuery
# export: dataset + nine rollout_* tables + *_latest views, created out
# of band with `bq mk` from the committed *.schema.json files in this
# directory. The exporter (bq_export.py) then only streams rows
# (ensure_schema=False, its default).
#
# The schema files are GENERATED from bq_export.py
# (`python3 ../bq_export.py emit-schemas`) and a parity test pins them
# to the module - regenerate + re-run this script after a model change.
# Re-running is safe: existing datasets/tables are left untouched
# (bq mk fails on existing; we detect and skip), and views are
# CREATE OR REPLACE.
#
# Usage: PROJECT_ID=my-project [DATASET=autocloud_rollout_intel] \
#        [LOCATION=US] ./setup-bq.sh
set -euo pipefail

PROJECT_ID=${PROJECT_ID:?set PROJECT_ID}
DATASET=${DATASET:-autocloud_rollout_intel}
LOCATION=${LOCATION:-US}
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$DATASET" == "autocloud_analysis" ]]; then
  echo "REFUSING: $DATASET is the harness dataset; the rollout-intel" >&2
  echo "export must use its own dataset (default autocloud_rollout_intel)" >&2
  exit 1
fi

echo "== dataset ${PROJECT_ID}:${DATASET}"
if bq show --dataset "${PROJECT_ID}:${DATASET}" > /dev/null 2>&1; then
  echo "   exists - leaving it untouched"
else
  bq mk --dataset \
    --location="${LOCATION}" \
    --description "Rollout reviewer episode store exports (append-only snapshots; read via *_latest views)" \
    --label created_by:rollout-intel-bq-export \
    "${PROJECT_ID}:${DATASET}"
fi

for schema in "${DIR}"/rollout_*.schema.json; do
  table="$(basename "${schema}" .schema.json)"
  echo "== table ${DATASET}.${table}"
  if bq show "${PROJECT_ID}:${DATASET}.${table}" > /dev/null 2>&1; then
    echo "   exists - leaving it untouched (schema changes: additive"
    echo "   'bq update --schema', or let ensure_dataset_and_tables"
    echo "   append the new NULLABLE columns)"
  else
    bq mk --table \
      --schema="${schema}" \
      --time_partitioning_field exported_at \
      --time_partitioning_type DAY \
      --description "rollout-intel episode export: ${table} snapshots (see ${table}_latest)" \
      "${PROJECT_ID}:${DATASET}.${table}"
  fi
done

echo "== views (*_latest, CREATE OR REPLACE)"
python3 "${DIR}/../bq_export.py" emit-views "${PROJECT_ID}" "${DATASET}" \
  | bq query --use_legacy_sql=false --project_id="${PROJECT_ID}"

echo "DONE - ${DATASET} ready; the exporter streams with ensure_schema=False."
