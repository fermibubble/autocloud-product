#!/usr/bin/env bash
# Minimal loop smoke: one deployment -> one episode -> four checkpoint
# sessions -> completed ladder with increasing report versions.
set -euo pipefail
WORLD="${WORLD_API:-http://127.0.0.1:7621}"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"

before=$(curl -s "$INTEL/intel/episodes" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
curl -s -X POST "$WORLD/world/deploy" -d '{"service":"demo-healthy"}' > /dev/null
echo "deployed demo-healthy; waiting for the ladder..."

for _ in $(seq 1 90); do
  count=$(curl -s "$INTEL/intel/episodes?status=awaiting_outcome" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
  total=$(curl -s "$INTEL/intel/episodes" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
  [ "$total" -gt "$before" ] && [ "$count" -gt 0 ] && break
  sleep 5
done

INTEL="$INTEL" python3 - <<'EOF'
import json, os, sys, urllib.request
INTEL = os.environ["INTEL"]
eps = json.load(urllib.request.urlopen(f"{INTEL}/intel/episodes?status=awaiting_outcome"))
assert eps, "no completed episode"
ep = eps[-1]
detail = json.load(urllib.request.urlopen(
    f"{INTEL}/intel/episodes/{ep['episode_id']}"))
cps = [c for c in detail["checkpoints"] if c["completed_at"]]
sessions = {c["session_id"] for c in cps}
versions = sorted(c["report_version"] for c in cps)
assert len(cps) == 4, f"expected 4 completed checkpoints, got {len(cps)}"
assert len(sessions) == 4, "each checkpoint must be its own session"
assert versions == [1, 2, 3, 4], f"report versions not monotonic: {versions}"
print(f"episode {ep['episode_id']}: 4 checkpoints, 4 sessions, reports {versions}, "
      f"final verdict {ep['final_verdict']}")
EOF
echo "RELAY SMOKE GREEN"
