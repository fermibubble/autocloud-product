#!/usr/bin/env bash
# End-to-end proof that this export executes on the current system.
# Sim mode only (LIVE_GCP unsupported here - the assertions depend on the
# sim's demo-errors scenario). Run ./scripts/run-stack.sh first, or let
# this script start it.
#
# What it proves, in order:
#   1. validator self-test        (schema <-> skill examples agree)
#   2. fixtures arm               (episode store writable, REST up)
#   3. world deploy               (sim fault activates: 5xx + injection)
#   4. gather                     (MCP tools reachable; signed bundle flows)
#   5. floor probe                (recorder REJECTS a softening verdict)
#   6. record                     (schema-valid record ACCEPTED)
#   7. validator --episode        (record + cross-refs + injection quoting)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
RUN="$ROOT/run"
EP="fx_eval_b_06"          # demo-errors, open T+30 checkpoint
STAGE="T+30"
INTEL="http://127.0.0.1:7611"
pass() { echo "PASS  $1"; }

curl -sf -m 2 "$INTEL/intel/health" > /dev/null 2>&1 || ./scripts/run-stack.sh

echo "== 1/7 validator self-test"
uv run --project servers/rollout-intel --with jsonschema \
  python scripts/validate-epistemic-record.py --self-test > /dev/null
pass "schema and skill worked-examples agree"

echo "== 2/7 arm fixtures"
curl -sf -X POST "$INTEL/intel/fixtures/load" \
  --data-binary @servers/rollout-intel/fixtures/eval-checkpoints.json > /dev/null
pass "12 fixture episodes armed"

echo "== 3/7 deploy demo-errors in the sim world"
curl -sf -X POST http://127.0.0.1:7621/world/deploy \
  -H 'Content-Type: application/json' -d '{"service":"demo-errors"}' > /dev/null
sleep 3
pass "deploy fired; fault active"

echo "== 4/7 gather (context pack + stage checks + log partition)"
rm -f "$RUN/trace.jsonl"
RUN_DIR="$RUN" uv run --project servers/rollout-intel \
  python examples/driver/session_driver.py gather "$EP" "$STAGE" > "$RUN/gather-output.txt"
grep -q '"policy_status": "fail"' "$RUN/gather-output.txt"
pass "signed bundle collected; policy evaluated fail (expected for demo-errors)"

echo "== 5/7 floor probe (softening verdict must be rejected)"
RUN_DIR="$RUN" uv run --project servers/rollout-intel \
  python examples/driver/session_driver.py probe "$EP" "$STAGE" > "$RUN/probe-output.txt"
grep -q "policy_conflict" "$RUN/probe-output.txt"
pass "recorder rejected 'healthy' against failing policy (policy_conflict)"

echo "== 6/7 build record from real evidence and record the checkpoint"
VERDICT=$(uv run --project servers/rollout-intel \
  python scripts/build-smoke-record.py "$RUN/trace.jsonl" "$RUN/report.md" "$RUN/summary.txt")
RUN_DIR="$RUN" uv run --project servers/rollout-intel \
  python examples/driver/session_driver.py record "$EP" "$STAGE" \
  "$RUN/report.md" "$RUN/summary.txt" "$VERDICT" > "$RUN/record-output.txt"
grep -q '"checkpoint_id"' "$RUN/record-output.txt"
pass "checkpoint recorded ($VERDICT)"

echo "== 7/7 validate the RECORDED checkpoint (cross-refs + injection quoting)"
uv run --project servers/rollout-intel --with jsonschema \
  python scripts/validate-epistemic-record.py \
  --episode "$EP" --intel "$INTEL" --require-quoted-evidence
pass "recorded epistemic record valid, injection quoted-not-obeyed"

echo
echo "SMOKE TEST PASSED - the export executes end-to-end on this system."
echo "Artifacts in run/: trace.jsonl, report.md, workspace/rollout-report.md"
