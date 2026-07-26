#!/usr/bin/env bash
# Generic per-agent eval suite runner: reads agents/<name>/evals/suite.yaml
# and drives each suite through the harness eval API, asserting every
# scored case's weighted total >= the suite's passThreshold.
#
# suite.yaml is a product convention (NOT a harness kind); it stays YAML so
# the bundle's datasets glob (agents/*/evals/*.json) never publishes it.
#
# Usage: run-suite.sh <agent-folder> [suite-name]
#   e.g. run-suite.sh rollout-reviewer golden
# Requires: gateway up, ENSEMBLE_TOKEN (autocloud tenant). Suites against a
# live model additionally need a runtime worker with ANTHROPIC_API_KEY;
# scripted suites need the worker's FAKE_SCRIPTS_DIR to include
# agents/rollout-reviewer/fake-scripts.
set -euo pipefail
cd "$(dirname "$0")"
API="${ENSEMBLE_API:-http://localhost:8088}"
: "${ENSEMBLE_TOKEN:?ENSEMBLE_TOKEN (autocloud tenant) required}"

AGENT="$(basename "${1:?usage: run-suite.sh <agent-folder> [suite-name]}")"
ONLY="${2:-}"
AGENT_DIR="../agents/$AGENT"
SUITE_FILE="$AGENT_DIR/evals/suite.yaml"
[ -f "$SUITE_FILE" ] || { echo "FAIL: no $SUITE_FILE"; exit 1; }

# PyYAML may be absent from the system python; uv is already the product's
# Python toolchain, so fall back to it.
PY="python3"
$PY -c "import yaml" 2>/dev/null || PY="uv run --with pyyaml python3"

# suite.yaml -> one TSV line per suite:
#   name \t agent \t dataset \t rubric \t threshold \t setup(json)
SUITES=$($PY - "$SUITE_FILE" <<'EOF'
import json, sys, yaml
doc = yaml.safe_load(open(sys.argv[1]))
for s in doc.get("suites", []):
    print("\t".join([
        s["name"],
        s.get("agent", doc["agent"]),
        s["dataset"],
        s["rubric"],
        str(s.get("passThreshold", 0.7)),
        json.dumps(s.get("setup", [])),
    ]))
EOF
)

FAILED=0
RAN=0
while IFS=$'\t' read -r NAME SAGENT DATASET RUBRIC THRESHOLD SETUP; do
  [ -z "$NAME" ] && continue
  if [ -n "$ONLY" ] && [ "$NAME" != "$ONLY" ]; then continue; fi
  RAN=$((RAN + 1))
  echo "== suite $AGENT/$NAME: agent=$SAGENT dataset=$DATASET rubric=$RUBRIC threshold=$THRESHOLD"

  # Setup commands run from the agent directory (stdin detached so they
  # cannot swallow the suite list feeding this loop).
  echo "$SETUP" | python3 -c "import json,sys; [print(c) for c in json.load(sys.stdin)]" | \
  while IFS= read -r CMD; do
    [ -z "$CMD" ] && continue
    echo "  setup: $CMD"
    (cd "$AGENT_DIR" && bash -c "$CMD") < /dev/null
  done

  RUN_ID=$(curl -s -X POST "$API/v1/evals/runs" \
    -H "Authorization: Bearer $ENSEMBLE_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"agent\":\"$SAGENT\",\"dataset\":\"$DATASET\",\"rubric\":\"$RUBRIC\"}" < /dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])") || {
    echo "  SUITE FAIL: could not create eval run"; FAILED=1; continue; }
  echo "  run: $RUN_ID"

  STATUS="running"
  for _ in $(seq 1 120); do
    STATUS=$(curl -s "$API/v1/evals/runs/$RUN_ID" -H "Authorization: Bearer $ENSEMBLE_TOKEN" < /dev/null \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")
    case "$STATUS" in completed|failed) break ;; esac
    sleep 5
  done
  echo "  status: $STATUS"
  if [ "$STATUS" != "completed" ]; then
    echo "  SUITE FAIL: $AGENT/$NAME run did not complete (status=$STATUS)"
    FAILED=1
    continue
  fi

  if curl -s "$API/v1/evals/runs/$RUN_ID/scores" -H "Authorization: Bearer $ENSEMBLE_TOKEN" < /dev/null \
    | THRESHOLD="$THRESHOLD" python3 -c "
import json, os, sys
d = json.load(sys.stdin)
cases = d.get('cases') or []
if not cases:
    print('  no scored cases'); sys.exit(1)
threshold = float(os.environ['THRESHOLD']) - 1e-9  # criterion weights are floats; 0.2+0.2+0.2+0.1+0.3 sums to 0.9999999999999999
ok = True
for c in cases:
    total = float(c.get('total', 0))
    mark = 'OK' if total >= threshold else 'FAIL'
    ok = ok and total >= threshold
    print(f\"  case {c.get('caseId')}: total={total:.2f} [{mark}]\")
sys.exit(0 if ok else 1)
"; then
    echo "  SUITE PASS: $AGENT/$NAME"
  else
    echo "  SUITE FAIL: $AGENT/$NAME (case below threshold $THRESHOLD)"
    FAILED=1
  fi
done <<< "$SUITES"

[ "$RAN" -gt 0 ] || { echo "FAIL: no suite matched '${ONLY}'"; exit 1; }
if [ "$FAILED" -eq 0 ]; then echo "SUITES GREEN"; else echo "SUITES RED"; exit 1; fi
