#!/usr/bin/env bash
# Time-correct replay evaluation over the labeled fixture corpus.
#
# For every corpus episode in chronological order, ask rollout-intel for
# the precedents it WOULD have retrieved at that episode's start time
# (as_of = started_at) and verify bitemporal correctness: nothing returned
# was labeled at-or-after that moment. Then score recorded verdicts
# against labels with false-safe weighted heaviest — a reviewer that says
# "healthy" about a rollout that regressed is the failure mode this whole
# system exists to prevent.
set -euo pipefail
cd "$(dirname "$0")"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"
CORPUS="../intel/fixtures/episodes-corpus.json"

echo "== loading corpus"
curl -s -X POST "$INTEL/intel/fixtures/load" --data-binary "@$CORPUS" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"  services={d['services']} episodes={d['episodes']}\")"

INTEL="$INTEL" CORPUS="$CORPUS" python3 - <<'EOF'
import json, os, sys, urllib.request

INTEL = os.environ["INTEL"]
corpus = json.load(open(os.environ["CORPUS"]))
episodes = sorted(corpus["episodes"], key=lambda e: e["started_at"])

print("== bitemporal correctness (precedents as_of each episode's start)")
violations = 0
for ep in episodes:
    url = f"{INTEL}/intel/precedents?episode={ep['episode_id']}&as_of={ep['started_at']}"
    result = json.load(urllib.request.urlopen(url))
    for p in result["healthy"] + result["unhealthy"]:
        if p["labeled_at"] >= ep["started_at"]:
            print(f"  VIOLATION: {ep['episode_id']} saw {p['episode_id']} "
                  f"labeled {p['labeled_at']} >= start {ep['started_at']}")
            violations += 1
print(f"  {len(episodes)} replayed retrievals, {violations} time violations")
assert violations == 0, "replay leaked future labels"

print("== decision quality (verdict vs label, false-safe weighted 10x)")
W_FALSE_SAFE, W_FALSE_HALT, W_INSUFFICIENT = 10.0, 1.0, 0.5
false_safe = false_halt = correct = insufficient = 0
for ep in episodes:
    v, label = ep["final_verdict"], ep["final_label"]
    bad = label in ("regressed", "rolled_back")
    if v == "healthy" and bad:
        false_safe += 1
    elif v == "regression-suspected" and not bad:
        false_halt += 1
    elif v == "insufficient-evidence":
        insufficient += 1
    else:
        correct += 1
cost = false_safe * W_FALSE_SAFE + false_halt * W_FALSE_HALT + insufficient * W_INSUFFICIENT
print(f"  labeled={len(episodes)} correct={correct} falseSafe={false_safe} "
      f"falseHalt={false_halt} insufficient={insufficient}")
print(f"  weighted cost = {false_safe}*{W_FALSE_SAFE} + {false_halt}*{W_FALSE_HALT} "
      f"+ {insufficient}*{W_INSUFFICIENT} = {cost}")

server = json.load(urllib.request.urlopen(f"{INTEL}/intel/metrics/decision-quality"))
print(f"== server decision-quality: labeled={server['labeledEpisodes']} "
      f"falseSafe={server['falseSafe']} falseHalt={server['falseHalt']}")
assert server["falseSafe"] >= false_safe, "server metric missed corpus false-safes"
EOF
echo "REPLAY RUN GREEN"
