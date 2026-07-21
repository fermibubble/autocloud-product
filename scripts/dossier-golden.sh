#!/usr/bin/env bash
# Phase-2 golden: the dossier layer end to end.
#
#   1. Governed writes: seed via propose->promote (the only write path).
#   2. Projection: active claims appear in memstore://project/rollout-dossiers.
#   3. Isolation: topicPrefix returns exactly one service's claims.
#   4. Supersession + bitemporal as_of: update a field; "now" reads the new
#      value, as_of before the promotion reads the old one.
#   5. Ambient read path: a live checkpoint session materializes the
#      read-only /memory mount and the reviewer reads dossier topics in it.
#
# Requires the P1 stack up (see golden-rollout.sh) plus ENSEMBLE_TOKEN.
set -euo pipefail
cd "$(dirname "$0")"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"
WORLD="${WORLD_API:-http://127.0.0.1:7621}"
API="${ENSEMBLE_API:-http://localhost:8088}"
: "${ENSEMBLE_TOKEN:?ENSEMBLE_TOKEN (autocloud tenant) required}"

./seed-dossiers.sh

echo "== supersession + as_of time travel"
T_BEFORE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sleep 2
REV=$(python3 intelctl.py propose --service demo-healthy --field p99_baseline_ms \
      --value 190 --type observed --rationale "golden: superseding update" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["rev_id"])')
python3 intelctl.py promote "$REV" --by dossier-golden > /dev/null

NOW_VAL=$(curl -s "$INTEL/intel/dossier?service=demo-healthy" \
  | python3 -c 'import json,sys; print([c["value"] for c in json.load(sys.stdin)["claims"] if c["field"]=="p99_baseline_ms"][0])')
OLD_VAL=$(curl -s "$INTEL/intel/dossier?service=demo-healthy&as_of=$T_BEFORE" \
  | python3 -c 'import json,sys; print([c["value"] for c in json.load(sys.stdin)["claims"] if c["field"]=="p99_baseline_ms"][0])')
echo "  now=$NOW_VAL as_of($T_BEFORE)=$OLD_VAL"
[ "$NOW_VAL" = "190" ] || { echo "FAIL: current value should be 190"; exit 1; }
[ "$OLD_VAL" = "185" ] || { echo "FAIL: as_of value should be 185"; exit 1; }

echo "== projection isolation via topicPrefix (and supersession in memory)"
STORES=$(curl -s -X POST "$API/v1/memory/resolve" -H "Authorization: Bearer $ENSEMBLE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent":"rollout-reviewer","stores":[{"ref":"memstore://project/rollout-dossiers"}]}' \
  | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["stores"][0]["store"]))')
API="$API" ENSEMBLE_TOKEN="$ENSEMBLE_TOKEN" STORES="$STORES" python3 - <<'EOF'
import json, os, urllib.request
req = urllib.request.Request(
    os.environ["API"] + "/v1/memory/search",
    data=json.dumps({"stores": [json.loads(os.environ["STORES"])], "query": "",
                     "topicPrefix": "dossier:demo-healthy.", "limit": 50}).encode(),
    method="POST")
req.add_header("Content-Type", "application/json")
req.add_header("Authorization", "Bearer " + os.environ["ENSEMBLE_TOKEN"])
ms = json.load(urllib.request.urlopen(req))["memories"]
topics = [m["topic"] for m in ms]
assert all(t.startswith("dossier:demo-healthy.") for t in topics), f"leak: {topics}"
p99 = [m for m in ms if m["topic"].endswith(":p99_baseline_ms")]
assert len(p99) == 1, f"supersession failed: {len(p99)} active p99 memories"
assert json.loads(p99[0]["content"])["value"] == 190, "projection not updated"
print(f"  {len(ms)} demo-healthy claims, one active per topic, updated value projected")
EOF

echo "== ambient read: live T+0 session reads the dossier mount"
T_DEPLOY=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -s -X POST "$WORLD/world/deploy" -d '{"service":"demo-healthy"}' > /dev/null
SESSION=""
for _ in $(seq 1 60); do
  # T+0 checkpoint session of the demo-healthy episode this deploy created
  # (started after T_DEPLOY; fixture episodes are excluded by the time gate).
  SESSION=$(INTEL="$INTEL" T_DEPLOY="$T_DEPLOY" python3 - <<'PYEOF'
import json, os, urllib.request
intel, t0 = os.environ["INTEL"], os.environ["T_DEPLOY"]
eps = [e for e in json.load(urllib.request.urlopen(f"{intel}/intel/episodes"))
       if "demo-healthy" in e["service_uid"] and e["started_at"] >= t0]
for ep in eps:
    d = json.load(urllib.request.urlopen(f"{intel}/intel/episodes/{ep['episode_id']}"))
    done = [c for c in d["checkpoints"] if c["stage"] == "T+0" and c.get("completed_at")]
    if done:
        print(done[0]["session_id"])
        break
PYEOF
) || true
  [ -n "$SESSION" ] && break
  sleep 5
done
[ -n "$SESSION" ] || { echo "FAIL: no completed T+0 session appeared"; exit 1; }
# /events is an SSE live-tail; bound the read and grep the captured replay.
EVENTS=$(curl -s -m 8 "$API/v1/sessions/$SESSION/events" \
  -H "Authorization: Bearer $ENSEMBLE_TOKEN" || true)
echo "$EVENTS" | grep -q "dossier:demo-healthy" \
  && echo "  session $SESSION read dossier topics from /memory mount" \
  || { echo "FAIL: session $SESSION shows no dossier mount read"; exit 1; }

echo "DOSSIER GOLDEN GREEN"
