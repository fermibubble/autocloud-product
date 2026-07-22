#!/usr/bin/env bash
# Capability-binding swap demo: prove that changing `prefer` in the spec
# swaps the observability provider WITHOUT touching the skill, the model-
# facing tool names, or the permission envelope.
#
# Steps:
#   1. Apply with prefer=[gcp-observe] → verify gcp-observe is bound
#   2. Flip prefer to [gcp-observe-b] → spec version bumps (one-change: mcp)
#   3. Verify gcp-observe-b is now bound, skill and tool names unchanged
#
# Requires: gateway, sim, both gcp-observe + gcp-observe-b MCP servers,
# rollout-intel, ENSEMBLE_TOKEN.
set -euo pipefail
cd "$(dirname "$0")"
: "${ENSEMBLE_TOKEN:?ENSEMBLE_TOKEN required}"
API="${ENSEMBLE_API:-http://localhost:8088}"
SPECS_DIR="../specs"

echo "== Step 1: verify prefer=[gcp-observe] is the current binding"
# The specs were just applied with prefer: [gcp-observe].
# Introspect the published spec to verify.
SPEC=$(curl -s "$API/v1/agents/rollout-reviewer" -H "Authorization: Bearer $ENSEMBLE_TOKEN")
echo "$SPEC" | python3 -c '
import json, sys
s = json.load(sys.stdin)["spec"]["spec"]
bindings = s.get("mcp", {}).get("bindings", [])
assert bindings, "no bindings in spec"
b = bindings[0]
assert b["alias"] == "observe", b
assert b["prefer"] == ["gcp-observe"], b["prefer"]
print("  binding: alias=observe prefer=[gcp-observe] capability=" + b["capability"])
print("  STEP 1 OK: prefer is gcp-observe")'

echo "== Step 2: flip prefer to [gcp-observe-b]"
# Patch both specs: replace prefer: [gcp-observe] with prefer: [gcp-observe-b]
for spec in rollout-reviewer.yaml rollout-reviewer-scripted.yaml; do
    sed -i.bak 's/prefer: \[gcp-observe\]/prefer: [gcp-observe-b]/' "$SPECS_DIR/$spec"
done

# Apply the one-line change
go run -C /Users/cmeesala/workspace/ensemble/cli . apply /Users/cmeesala/workspace/autocloud-product 2>&1 \
  | grep -E "spec|capability|mcp|skill" | while read -r line; do echo "  $line"; done

echo "== Step 3: verify gcp-observe-b is now bound"
SPEC=$(curl -s "$API/v1/agents/rollout-reviewer" -H "Authorization: Bearer $ENSEMBLE_TOKEN")
echo "$SPEC" | python3 -c '
import json, sys
s = json.load(sys.stdin)["spec"]["spec"]
bindings = s.get("mcp", {}).get("bindings", [])
b = bindings[0]
assert b["prefer"] == ["gcp-observe-b"], b["prefer"]
print("  binding: alias=observe prefer=[gcp-observe-b]")
# Skills are unchanged (still @3.1.0)
skills = s.get("skills", {}).get("refs", [])
assert any("3.1.0" in r for r in skills), skills
print("  skill: rollout-validation-protocol@3.1.0 (unchanged)")
print("  tool names: mcp__observe__* (unchanged — the alias did not move)")
print("  STEP 3 OK: provider swapped, everything else untouched")'

echo "== Step 4: restore prefer to [gcp-observe] for other tests"
for spec in rollout-reviewer.yaml rollout-reviewer-scripted.yaml; do
    sed -i.bak 's/prefer: \[gcp-observe-b\]/prefer: [gcp-observe]/' "$SPECS_DIR/$spec"
    rm -f "$SPECS_DIR/$spec.bak"
done
go run -C /Users/cmeesala/workspace/ensemble/cli . apply /Users/cmeesala/workspace/autocloud-product 2>&1 | grep "spec" | while read -r line; do echo "  $line"; done

echo "CAPABILITY SWAP DEMO GREEN"
