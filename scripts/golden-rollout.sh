#!/usr/bin/env bash
# The rollout golden regression: deploy all four fixture services through
# the REAL loop (relay -> episodes -> checkpoint sessions -> signed
# evidence -> deterministic policy -> recorded verdicts) and assert
# GROUND TRUTH against rollout-intel — verdicts must match what the
# seeded world actually did, every observation must be signature-verified,
# and thin evidence must yield insufficient-evidence, never healthy.
#
# Requires up: harness services, gcp_sim (7620/7621), gcp-observe sim mode
# (7600/7601), rollout-intel (7610/7611), relay (SIM_TIME_SCALE<=0.02),
# runtime worker with autocloud fake-scripts on FAKE_SCRIPTS_DIR, and an
# autocloud-tenant ENSEMBLE_TOKEN exported.
set -euo pipefail
WORLD="${WORLD_API:-http://127.0.0.1:7621}"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"

SERVICES=(demo-healthy demo-latency demo-errors demo-thin)

echo "== deploying ${#SERVICES[@]} fixture services"
for svc in "${SERVICES[@]}"; do
  curl -s -X POST "$WORLD/world/deploy" -d "{\"service\":\"$svc\"}" > /dev/null
  sleep 2   # stagger so per-service checkpoint resolution stays unambiguous
done

echo "== waiting for all episodes to complete their ladders"
for _ in $(seq 1 120); do
  done_count=$(curl -s "$INTEL/intel/episodes?status=awaiting_outcome" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
  [ "$done_count" -ge "${#SERVICES[@]}" ] && break
  sleep 5
done

echo "== ground truth"
INTEL="$INTEL" python3 - <<'EOF'
import json, os, sys, urllib.request

INTEL = os.environ["INTEL"]
EXPECTED = {
    "demo-healthy": "healthy",
    "demo-latency": "regression-suspected",
    "demo-errors": "regression-suspected",
    "demo-thin": "insufficient-evidence",
}
all_eps = json.load(urllib.request.urlopen(f"{INTEL}/intel/episodes"))
episodes = [e for e in all_eps if e["status"] == "awaiting_outcome"]
by_service = {}
for e in episodes:
    name = e["service_uid"].split("/")[-3]
    by_service.setdefault(name, e)  # first completed episode per service

failures = []
for name, want in EXPECTED.items():
    ep = by_service.get(name)
    if not ep:
        failures.append(f"{name}: no completed episode")
        continue
    got = ep["final_verdict"]
    detail = json.load(urllib.request.urlopen(
        f"{INTEL}/intel/episodes/{ep['episode_id']}"))
    cps = [c for c in detail["checkpoints"] if c["completed_at"]]
    versions = sorted(c["report_version"] for c in cps)
    unverified = [o for o in detail["observations"] if not o["sig_verified"]]
    status = "OK" if got == want else "WRONG"
    print(f"  {name:14s} verdict={got:24s} want={want:24s} "
          f"checkpoints={len(cps)} reports={versions} unverified_obs={len(unverified)} [{status}]")
    if got != want:
        failures.append(f"{name}: verdict {got} != {want}")
    if len(cps) != 4 or versions != [1, 2, 3, 4]:
        failures.append(f"{name}: checkpoint ladder incomplete {versions}")
    if unverified:
        failures.append(f"{name}: {len(unverified)} unverified observations")

if failures:
    print("FAILURES:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("all episodes correct: verdicts match world truth, ladders complete, all evidence signed")
EOF
echo "ROLLOUT GOLDEN GREEN"
