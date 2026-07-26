#!/usr/bin/env bash
# Generic per-agent eval suite runner: reads agents/<name>/evals/suite.yaml
# and drives each suite through the harness eval API, asserting every
# scored case's weighted total >= each rubric's passThreshold.
#
# A suite binds ONE dataset to ONE OR MORE rubrics. Sessions execute once;
# every rubric grades the same sessions (scoring v2) — rubric count is not
# a cost axis. Two suite forms are accepted:
#   rubric: rollout-review@2          # single rubric + passThreshold
#   rubrics:                          # multi-rubric, per-rubric thresholds
#     - { ref: rollout-review@2,          passThreshold: 1.0 }
#     - { ref: rollout-reviewer-tenets@2, passThreshold: 0.8 }
#
# suite.yaml is a product convention (NOT a harness kind); it stays YAML so
# the bundle's datasets glob (agents/*/evals/*.json) never publishes it.
#
# Usage: run-suite.sh <agent-folder> [suite-name]
#   e.g. run-suite.sh rollout-reviewer golden
# Requires: gateway up, ENSEMBLE_TOKEN (autocloud tenant). Suites against a
# live model additionally need a runtime worker with ANTHROPIC_API_KEY;
# judge-scored rubrics need an eval worker with ANTHROPIC_API_KEY too
# (judge criteria are withheld, never fabricated, without one); scripted
# suites need the worker's FAKE_SCRIPTS_DIR to include
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
#   name \t agent \t dataset \t rubrics(json: [{ref, threshold}]) \t setup(json)
SUITES=$($PY - "$SUITE_FILE" <<'EOF'
import json, sys, yaml
doc = yaml.safe_load(open(sys.argv[1]))
for s in doc.get("suites", []):
    if "rubrics" in s:
        rubrics = [{"ref": r["ref"],
                    "threshold": float(r.get("passThreshold", s.get("passThreshold", 0.7)))}
                   for r in s["rubrics"]]
    else:
        rubrics = [{"ref": s["rubric"], "threshold": float(s.get("passThreshold", 0.7))}]
    print("\t".join([
        s["name"],
        s.get("agent", doc["agent"]),
        s["dataset"],
        json.dumps(rubrics),
        json.dumps(s.get("setup", [])),
    ]))
EOF
)

FAILED=0
RAN=0
while IFS=$'\t' read -r NAME SAGENT DATASET RUBRICS SETUP; do
  [ -z "$NAME" ] && continue
  if [ -n "$ONLY" ] && [ "$NAME" != "$ONLY" ]; then continue; fi
  RAN=$((RAN + 1))
  echo "== suite $AGENT/$NAME: agent=$SAGENT dataset=$DATASET rubrics=$RUBRICS"

  # Setup commands run from the agent directory (stdin detached so they
  # cannot swallow the suite list feeding this loop).
  echo "$SETUP" | python3 -c "import json,sys; [print(c) for c in json.load(sys.stdin)]" | \
  while IFS= read -r CMD; do
    [ -z "$CMD" ] && continue
    echo "  setup: $CMD"
    (cd "$AGENT_DIR" && bash -c "$CMD") < /dev/null
  done

  REQ=$(RUBRICS="$RUBRICS" python3 -c "
import json, os
rubrics = json.loads(os.environ['RUBRICS'])
print(json.dumps({'agent': '$SAGENT', 'dataset': '$DATASET',
                  'rubrics': [r['ref'] for r in rubrics]}))")
  RUN_ID=$(curl -s -X POST "$API/v1/evals/runs" \
    -H "Authorization: Bearer $ENSEMBLE_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$REQ" < /dev/null \
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
    | RUBRICS="$RUBRICS" python3 -c "
import json, os, sys
d = json.load(sys.stdin)
wanted = {r['ref']: r['threshold'] for r in json.loads(os.environ['RUBRICS'])}
per_rubric = {r.get('rubric'): r.get('cases') or [] for r in (d.get('rubrics') or [])}
if not per_rubric:
    # Pre-scoring-v2 gateway: single flat cases list, single rubric.
    per_rubric = {next(iter(wanted)): d.get('cases') or []}
ok = True
for ref, threshold in wanted.items():
    # The gateway stores resolved refs (name@N); a versionless request ref
    # matches by name prefix.
    cases = per_rubric.get(ref)
    if cases is None:
        matches = [c for k, c in per_rubric.items() if k and k.split('@')[0] == ref.split('@')[0]]
        cases = matches[0] if matches else None
    if not cases:
        print(f'  rubric {ref}: no scored cases'); ok = False; continue
    bar = threshold - 1e-9  # criterion weights are floats; sums land at 0.9999999999999999
    for c in cases:
        total = float(c.get('total', 0))
        gated = ' GATED' if c.get('gated') else ''
        mark = 'OK' if total >= bar else 'FAIL'
        ok = ok and total >= bar
        print(f\"  rubric {ref} case {c.get('caseId')}: total={total:.2f}{gated} [{mark}]\")
sys.exit(0 if ok else 1)
"; then
    echo "  SUITE PASS: $AGENT/$NAME"
  else
    echo "  SUITE FAIL: $AGENT/$NAME (case below a rubric threshold)"
    FAILED=1
  fi
done <<< "$SUITES"

[ "$RAN" -gt 0 ] || { echo "FAIL: no suite matched '${ONLY}'"; exit 1; }
if [ "$FAILED" -eq 0 ]; then echo "SUITES GREEN"; else echo "SUITES RED"; exit 1; fi
