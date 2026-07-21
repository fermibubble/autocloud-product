#!/usr/bin/env bash
# One-change experiment: rollout-validation-protocol skill 2.0.0 vs 3.0.0
# (precedent consultation) on the rollout-golden dataset. `skills` is the
# ONLY section that differs between the scripted reviewer versions under
# test, so the harness's one-change gate accepts the comparison.
#
# Eval sessions have no relay, so rollout-intel is pre-armed with fixture
# episodes carrying one open checkpoint per (case, arm) — the scripted
# reviewer resolves them by service name, oldest first (fx_ semantics).
#
# Usage: BASE=2 CANDIDATE=3 ./experiment-run.sh   (defaults shown)
set -euo pipefail
cd "$(dirname "$0")"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"
CLI="${ENSEMBLE_CLI:-go run -C ../../ensemble/cli .}"
: "${ENSEMBLE_TOKEN:?ENSEMBLE_TOKEN (autocloud tenant) required}"
BASE="${BASE:-2}"
CANDIDATE="${CANDIDATE:-3}"

echo "== arming eval checkpoints"
curl -s -X POST "$INTEL/intel/fixtures/load" \
  --data-binary "@../intel/fixtures/eval-checkpoints.json" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"  episodes={d['episodes']} open_checkpoints={d['checkpoints']}\")"

echo "== experiment: rollout-reviewer-scripted @$BASE vs @$CANDIDATE (skills section only)"
OUT=$($CLI experiment run --agent rollout-reviewer-scripted \
      --base "$BASE" --candidate "$CANDIDATE" \
      --dataset rollout-golden --rubric rollout-review@2)
echo "$OUT"
EXP_ID=$(echo "$OUT" | sed -n 's/^experiment \([A-Za-z0-9]*\) .*/\1/p' | head -1)
[ -n "$EXP_ID" ] || { echo "FAIL: no experiment id in output"; exit 1; }

echo "== waiting for report ($EXP_ID)"
for _ in $(seq 1 120); do
  REPORT=$($CLI experiment report "$EXP_ID" 2>/dev/null || true)
  echo "$REPORT" | grep -qiE 'status.*(complete|passed|failed|ready)' && break
  sleep 5
done
echo "$REPORT"
echo "EXPERIMENT RUN DONE"
