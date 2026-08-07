#!/usr/bin/env bash
# Fast-Forward arm comparison: arm C (FF_MODE=signal_only — counter/slope
# projection only, probes never run) vs arm D (FF_MODE=full — the
# Signal->Probe escalation). Each arm resets the world, deploys all seven
# fixture services, waits out the ladders, and prints a small table:
# delayed-regression recall over leak/retry/cred, false blocks over the
# rest, median seconds from FF request creation to terminal, and budget
# spent. A comparison report, not a golden — it asserts only that the
# ladders completed.
#
# EXPECTED HEADLINE: arm C catches demo-leak via signal projection (the
# open_connections slope crosses the handle threshold inside the horizon)
# but MISSES demo-cred — stale-credential reuse after key rotation is an
# event-sequence-only hazard no projected counter exposes; arm D catches
# all three of leak/retry/cred.
#
# Process management follows the golden convention: services are
# PRE-STARTED by the operator, so this script cannot flip FF_MODE itself —
# it prints the restart instruction and waits for confirmation.
#
# Requires up: harness services, gcp_sim (7620/7621), probe target (7640),
# gcp-observe sim mode (7600/7601), rollout-intel (7610/7611) with policy
# rollout-slo v2, fastforward (7630/7631), relay + outcome collector,
# runtime worker, and an autocloud-tenant ENSEMBLE_TOKEN exported.
set -euo pipefail
cd "$(dirname "$0")"
WORLD="${WORLD_API:-http://127.0.0.1:7621}"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"
FF="${FF_API:-http://127.0.0.1:7631}"

SERVICES=(demo-leak demo-retry demo-cred demo-healthy demo-latency demo-errors demo-thin)

run_arm() {
  local arm="$1"
  echo "== arm $arm: resetting world (seed 42)"
  curl -sf -X POST "$WORLD/world/reset" -d '{"seed":42}' > /dev/null
  sleep 5   # the relay tracks the feed by length; let it see the emptied feed
  FF_API="$FF" ./ff-seed-profiles.sh > /dev/null

  local t_start
  t_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "== arm $arm: deploying ${#SERVICES[@]} services"
  local svc
  for svc in "${SERVICES[@]}"; do
    curl -s -X POST "$WORLD/world/deploy" -d "{\"service\":\"$svc\"}" > /dev/null
    sleep 2   # stagger so per-service checkpoint resolution stays unambiguous
  done

  echo "== arm $arm: waiting for all episodes to complete their ladders"
  local done_count=0
  for _ in $(seq 1 240); do
    done_count=$(INTEL="$INTEL" T_START="$t_start" python3 -c "
import json, os, urllib.request
eps = json.load(urllib.request.urlopen(os.environ['INTEL'] + '/intel/episodes'))
print(len([e for e in eps
           if e['status'] in ('awaiting_outcome', 'closed')
           and not e['episode_id'].startswith('fx_')
           and e['started_at'] >= os.environ['T_START']]))")
    [ "$done_count" -ge "${#SERVICES[@]}" ] && break
    sleep 5
  done
  if [ "$done_count" -lt "${#SERVICES[@]}" ]; then
    echo "FAIL: arm $arm ladders incomplete ($done_count/${#SERVICES[@]})"
    exit 1
  fi

  INTEL="$INTEL" FF="$FF" T_START="$t_start" ARM="$arm" python3 - <<'EOF'
import datetime, json, os, statistics, urllib.request

INTEL = os.environ["INTEL"]
FF = os.environ["FF"]
T_START = os.environ["T_START"]
ARM = os.environ["ARM"]

# What the world truly does; a "false block" is regression-suspected on a
# service whose correct verdict is anything else (demo-latency/demo-errors
# regress immediately — blocking them is right, not false).
EXPECTED = {
    "demo-leak": "regression-suspected",
    "demo-retry": "regression-suspected",
    "demo-cred": "regression-suspected",
    "demo-healthy": "healthy",
    "demo-latency": "regression-suspected",
    "demo-errors": "regression-suspected",
    "demo-thin": "insufficient-evidence",
}
DELAYED = ("demo-leak", "demo-retry", "demo-cred")

def get(url):
    return json.load(urllib.request.urlopen(url))

def parse(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")

episodes = [e for e in get(f"{INTEL}/intel/episodes")
            if e["status"] in ("awaiting_outcome", "closed")
            and not e["episode_id"].startswith("fx_")
            and e["started_at"] >= T_START]
by_service = {}
for e in episodes:
    by_service.setdefault(e["service_uid"].split("/")[-3], e)

rows, ttds, spent = [], [], []
caught = false_blocks = 0
for name, want in EXPECTED.items():
    ep = by_service.get(name)
    verdict = ep["final_verdict"] if ep else "-"
    outcome, ttd, budget = "-", None, None
    if ep:
        try:
            envs = get(f"{FF}/ff/episodes/{ep['episode_id']}/result-envelopes"
                       ).get("envelopes", [])
        except Exception:
            envs = []
        results = [e for e in envs if e.get("type") == "fastforward_result"]
        if results:
            payload = results[0]["payload"]
            outcome = payload.get("outcome", "-")
            budget = (payload.get("budget") or {}).get("spent")
            try:
                packet = get(f"{FF}/ff/requests/{payload['request_id']}")
                snap = packet.get("snapshot") or {}
                if isinstance(snap, str):
                    snap = json.loads(snap or "{}")
                created = packet.get("created_at") or snap.get("created_at")
                decided = packet.get("decided_at") or snap.get("decided_at")
                if created and decided:
                    ttd = (parse(decided) - parse(created)).total_seconds()
            except Exception:
                pass
    if name in DELAYED and verdict == "regression-suspected":
        caught += 1
    if want != "regression-suspected" and verdict == "regression-suspected":
        false_blocks += 1
    if ttd is not None:
        ttds.append(ttd)
    if name in DELAYED:
        spent.append((name, budget))
    rows.append((name, verdict, outcome, ttd, budget))

print(f"  arm {ARM}:")
print(f"  {'service':14s} {'verdict':24s} {'ff_outcome':28s} {'ttd_s':>7s} budget_spent")
for name, verdict, outcome, ttd, budget in rows:
    ttd_s = f"{ttd:.1f}" if ttd is not None else "-"
    print(f"  {name:14s} {verdict:24s} {outcome:28s} {ttd_s:>7s} "
          + json.dumps(budget, separators=(",", ":")))
median = f"{statistics.median(ttds):.1f}s" if ttds else "n/a"
print(f"  arm {ARM}: delayed-regression recall {caught}/3, "
      f"false blocks {false_blocks}, median request->terminal {median}, "
      "budget spent (delayed set) "
      + json.dumps(dict(spent), separators=(",", ":")))
EOF
}

echo "ARM C needs the fastforward service running with FF_MODE=signal_only."
echo "Restart it now, then press enter to continue."
read -r _
curl -sf "$FF/ff/health" > /dev/null || { echo "FAIL: fastforward $FF unreachable"; exit 1; }
run_arm C

echo "ARM D needs the fastforward service running with FF_MODE=full."
echo "Restart it now, then press enter to continue."
read -r _
curl -sf "$FF/ff/health" > /dev/null || { echo "FAIL: fastforward $FF unreachable"; exit 1; }
run_arm D

echo "FF ARMS DONE"
