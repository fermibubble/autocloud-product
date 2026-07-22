#!/usr/bin/env bash
# Phase-4 golden: conservative learning end to end.
#
#   1. Load the labeled corpus (support can only come from LABELED episodes).
#   2. Agent-style proposals citing 2 labeled episodes -> NO suggestion
#      (below the recurrence threshold).
#   3. A third labeled citation -> the claim becomes a suggestion.
#   4. A rival proposal with labeled support -> BOTH blocked (contradiction).
#   5. Human promotes the surviving suggestion via intelctl -> claim active.
#   6. Signal utility runs over labeled decisions and ranks signals.
set -euo pipefail
cd "$(dirname "$0")"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"

echo "== loading labeled corpus"
curl -s -X POST "$INTEL/intel/fixtures/load" --data-binary "@../intel/fixtures/episodes-corpus.json" > /dev/null

# Idempotence: clear any deploy_risk_note leftovers from earlier runs so
# recurrence counting starts from zero.
INTEL="$INTEL" python3 - <<'EOF'
import json, os, urllib.request
intel = os.environ["INTEL"]
journal = json.load(urllib.request.urlopen(f"{intel}/intel/dossier/journal?service=checkout-api"))
for rev in journal:
    # An ACTIVE leftover with the same value is harmless (same-value
    # claims don't contradict); only open proposals skew recurrence.
    if rev["field"] == "deploy_risk_note" and rev["status"] == "proposed":
        req = urllib.request.Request(
            f"{intel}/intel/dossier/{rev['rev_id']}/reject",
            data=b'{"actor":"learning-golden-cleanup"}', method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req)
EOF

propose() { # field value sources_json
  curl -s -X POST "$INTEL/intel/dossier/propose" -d "{
    \"service\": \"checkout-api\", \"field\": \"$1\", \"value\": $2,
    \"epistemic_type\": \"hypothesized\", \"sources\": $3,
    \"rationale\": \"learning-golden\"}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["rev_id"])'
}
suggestions() {
  curl -s "$INTEL/intel/learning/suggestions"
}

echo "== below threshold: 2 labeled citations"
propose deploy_risk_note '"binary-only deploys stabilize fast"' '["fx_ep_016","fx_ep_017"]' > /dev/null
COUNT=$(suggestions | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["suggestions"]))')
[ "$COUNT" = "0" ] || { echo "FAIL: suggested below recurrence threshold"; exit 1; }
echo "  no suggestion (correct)"

echo "== at threshold: third labeled citation"
REV=$(propose deploy_risk_note '"binary-only deploys stabilize fast"' '["fx_ep_018"]')
S=$(suggestions)
echo "$S" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert len(d["suggestions"])==1, d
s=d["suggestions"][0]
assert s["support"]==3 and s["field"]=="deploy_risk_note", s
print("  suggested:", s["field"], "support=%d" % s["support"], "episodes=", s["support_episodes"])'

echo "== contradiction: rival value with labeled support blocks both"
propose deploy_risk_note '"binary deploys are risky"' '["fx_ep_019"]' > /dev/null
suggestions | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d["suggestions"]==[], "contradicted claim still suggested"
kinds={b["kind"] for e in d["blocked"] for b in e["blocked_by"]}
assert "rival_proposal" in kinds
print("  blocked by rival_proposal (correct)")'

echo "== human promotes the well-supported revision anyway (their call)"
python3 intelctl.py promote "$REV" --by learning-golden > /dev/null
curl -s "$INTEL/intel/dossier?service=checkout-api" | python3 -c '
import json,sys
claims=json.load(sys.stdin)["claims"]
assert any(c["field"]=="deploy_risk_note" and c["status"]=="active" for c in claims)
print("  claim active after human promotion")'

echo "== signal utility over labeled decisions"
curl -s "$INTEL/intel/learning/signal-utility" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("  scored=%d abstentions=%d" % (d["scored_decisions"], d["abstentions_skipped"]))
for r in d["policy_rules"][:3]:
    print("  rule %s: correct=%d incorrect=%d utility=%s" % (r["signal"], r["correct"], r["incorrect"], r["utility"]))'

echo "LEARNING GOLDEN GREEN"
