#!/usr/bin/env bash
# The Fast-Forward golden: three seeded DELAYED-fault services (demo-leak,
# demo-retry, demo-cred) whose ladder-window telemetry stays healthy must
# be blocked at T+30 anyway — by a verified fastforward_result envelope
# carrying outcome temporal_counterexample, minted from a terminal
# COUNTEREXAMPLE request with a replay-verified counterexample, decided
# BEFORE the T+30 record — while the healthy control is never falsely
# blocked and thin evidence stays insufficient-evidence. Then the scaled
# 24h outcome horizon must prove the world really did regress
# (delayed-regression recall 3/3): the block was foresight, not paranoia.
#
# Requires up: harness services, gcp_sim (7620/7621), probe target (7640),
# gcp-observe sim mode (7600/7601), rollout-intel (7610/7611) with policy
# rollout-slo v2, fastforward (7630/7631, FF_MODE=full), relay + outcome
# collector, runtime worker with agents/rollout-reviewer/fake-scripts on
# FAKE_SCRIPTS_DIR, and an autocloud-tenant ENSEMBLE_TOKEN exported.
set -euo pipefail
cd "$(dirname "$0")"
WORLD="${WORLD_API:-http://127.0.0.1:7621}"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"
FF="${FF_API:-http://127.0.0.1:7631}"
PROBE="${PROBE_API:-http://127.0.0.1:7640}"
SCALE="${SIM_TIME_SCALE:-0.02}"
SEED="${WORLD_SEED:-42}"

echo "== preflight"
curl -sf "$WORLD/world/seed" > /dev/null || { echo "FAIL: world $WORLD unreachable"; exit 1; }
curl -sf "$INTEL/intel/health" > /dev/null || { echo "FAIL: intel $INTEL unreachable"; exit 1; }
curl -sf "$FF/ff/health" > /dev/null || { echo "FAIL: fastforward $FF unreachable"; exit 1; }
# The probe target exposes no health endpoint; any HTTP response (even a
# 404 for a bogus instance) proves the process is listening.
curl -s -o /dev/null "$PROBE/probe/instances/preflight/counters" \
  || { echo "FAIL: probe target $PROBE unreachable"; exit 1; }

# SIM_TIME_SCALE operator contract: the sim world, the relay, the outcome
# collector, and this script each read SIM_TIME_SCALE from their OWN
# environment — the world deliberately exposes no time-scale endpoint
# (goldens add no endpoints). If /world/seed ever grows a time_scale
# field we compare against it; until then the operator MUST export ONE
# identical value to every process and to this script, which sizes the
# outcome-horizon wait from it. A mismatch silently desynchronizes ladder
# timing from ground-truth fault timing.
WORLD="$WORLD" SCALE="$SCALE" python3 - <<'EOF'
import json, os, sys, urllib.request
seed = json.load(urllib.request.urlopen(os.environ["WORLD"] + "/world/seed"))
reported = seed.get("time_scale", seed.get("sim_time_scale"))
if reported is not None and abs(float(reported) - float(os.environ["SCALE"])) > 1e-9:
    print(f"FAIL: world time_scale {reported} != SIM_TIME_SCALE {os.environ['SCALE']}")
    sys.exit(1)
print(f"  SIM_TIME_SCALE={os.environ['SCALE']}"
      + (" (world agrees)" if reported is not None
         else " (world does not report it; operator contract applies)"))
EOF

echo "== resetting world (seed $SEED)"
curl -sf -X POST "$WORLD/world/reset" -d "{\"seed\":$SEED}" > /dev/null
sleep 5   # the relay tracks the feed by length; let it see the emptied feed

FF_API="$FF" ./ff-seed-profiles.sh

SERVICES=(demo-leak demo-retry demo-cred demo-healthy demo-thin)
T_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "== deploying ${#SERVICES[@]} services"
for svc in "${SERVICES[@]}"; do
  curl -s -X POST "$WORLD/world/deploy" -d "{\"service\":\"$svc\"}" > /dev/null
  sleep 2   # stagger so per-service checkpoint resolution stays unambiguous
done

echo "== waiting for all episodes to complete their ladders"
for _ in $(seq 1 240); do
  done_count=$(INTEL="$INTEL" T_START="$T_START" python3 -c "
import json, os, urllib.request
NAMES = {'demo-leak', 'demo-retry', 'demo-cred', 'demo-healthy', 'demo-thin'}
eps = json.load(urllib.request.urlopen(os.environ['INTEL'] + '/intel/episodes'))
print(len([e for e in eps
           if e['status'] in ('awaiting_outcome', 'closed')
           and not e['episode_id'].startswith('fx_')
           and e['started_at'] >= os.environ['T_START']
           and e['service_uid'].split('/')[-3] in NAMES]))")
  [ "$done_count" -ge "${#SERVICES[@]}" ] && break
  sleep 5
done

echo "== ground truth at T+30"
INTEL="$INTEL" FF="$FF" T_START="$T_START" python3 - <<'EOF'
import hashlib, hmac, json, os, sys, urllib.request

INTEL = os.environ["INTEL"]
FF = os.environ["FF"]
T_START = os.environ["T_START"]
# The golden runs operator-side, where the signing key legitimately lives
# (it never enters a sandbox) — so it can re-verify FF envelopes itself
# rather than trusting rollout-intel's sig_verified flag alone.
KEY = os.environ.get("OBS_SIGNING_KEY", "dev-observation-key").encode()

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

def verify_envelope(env: dict) -> bool:
    basis = {k: env.get(k) for k in ("observation_id", "type", "scope",
                                     "observed_at", "fresh_until", "content_hash")}
    if hmac.new(KEY, canonical(basis), hashlib.sha256).hexdigest() != env.get("sig"):
        return False
    return env.get("content_hash") == \
        "sha256:" + hashlib.sha256(canonical(env.get("payload"))).hexdigest()

def get(url):
    return json.load(urllib.request.urlopen(url))

EXPECTED = {
    "demo-leak": "regression-suspected",
    "demo-retry": "regression-suspected",
    "demo-cred": "regression-suspected",
    "demo-healthy": "healthy",
    "demo-thin": "insufficient-evidence",
}
FAULTED = ("demo-leak", "demo-retry", "demo-cred")

all_eps = get(f"{INTEL}/intel/episodes")
episodes = [e for e in all_eps
            if e["status"] in ("awaiting_outcome", "closed")
            and not e["episode_id"].startswith("fx_")
            and e["started_at"] >= T_START]
by_service = {}
for e in episodes:
    by_service.setdefault(e["service_uid"].split("/")[-3], e)

def ff_result(episode_id):
    """(fastforward_result envelope, terminal request packet) or (None, None)."""
    try:
        envs = get(f"{FF}/ff/episodes/{episode_id}/result-envelopes").get("envelopes", [])
    except Exception:
        return None, None
    results = [e for e in envs if e.get("type") == "fastforward_result"]
    if not results:
        return None, None
    env = results[0]
    packet = get(f"{FF}/ff/requests/{env['payload']['request_id']}")
    return env, packet

failures = []
false_block = 0
unverified_total = 0
for name, want in EXPECTED.items():
    ep = by_service.get(name)
    if not ep:
        failures.append(f"{name}: no completed episode")
        continue
    got = ep["final_verdict"]
    detail = get(f"{INTEL}/intel/episodes/{ep['episode_id']}")
    unverified = [o for o in detail["observations"] if not o["sig_verified"]]
    unverified_total += len(unverified)
    if unverified:
        failures.append(f"{name}: {len(unverified)} unverified observations")
    if got != want:
        failures.append(f"{name}: verdict {got} != {want}")
    if name not in FAULTED and got == "regression-suspected":
        false_block += 1

    env, packet = ff_result(ep["episode_id"])
    outcome = env["payload"].get("outcome") if env else None
    print(f"  {name:12s} verdict={got:24s} want={want:24s} "
          f"ff={outcome or '-':28s} [{'OK' if got == want else 'WRONG'}]")

    if name in FAULTED:
        t30 = next((c for c in detail["checkpoints"]
                    if c["stage"] == "T+30" and c["completed_at"]), None)
        if t30 is None:
            failures.append(f"{name}: no completed T+30 checkpoint")
            continue
        ff_obs = [o for o in detail["observations"]
                  if o["type"] == "fastforward_result" and o["sig_verified"]
                  and o["checkpoint_id"] == t30["checkpoint_id"]]
        if not ff_obs:
            failures.append(f"{name}: T+30 recorded no verified fastforward_result observation")
        if env is None:
            failures.append(f"{name}: no fastforward_result envelope from FF")
            continue
        if not verify_envelope(env):
            failures.append(f"{name}: fastforward_result envelope fails local verification")
        if env["scope"].get("service") != name:
            failures.append(f"{name}: envelope scope.service {env['scope'].get('service')!r}")
        if outcome != "temporal_counterexample":
            failures.append(f"{name}: FF outcome {outcome} != temporal_counterexample")
        if packet.get("state") != "COUNTEREXAMPLE":
            failures.append(f"{name}: FF request state {packet.get('state')} != COUNTEREXAMPLE")
        verified_cx = [c for c in (packet.get("counterexamples") or [])
                       if c.get("replay_verified") in (1, True)]
        if not verified_cx:
            failures.append(f"{name}: no counterexample with replay_verified=1")
        snap = packet.get("snapshot") or {}
        if isinstance(snap, str):
            try:
                snap = json.loads(snap)
            except ValueError:
                snap = {}
        decided = packet.get("decided_at") or snap.get("decided_at")
        # <= not <: both clocks are 1s-resolution UTC ISO; a same-second
        # decide+record still means the decision preceded the record.
        if not decided:
            failures.append(f"{name}: FF packet carries no decided_at")
        elif decided > t30["completed_at"]:
            failures.append(f"{name}: FF decided_at {decided} after "
                            f"T+30 record {t30['completed_at']}")
    elif name == "demo-healthy":
        if outcome != "no_material_temporal_hazard":
            failures.append(f"demo-healthy: FF outcome {outcome} != no_material_temporal_hazard")
        if env is not None and not verify_envelope(env):
            failures.append("demo-healthy: fastforward_result envelope fails local verification")

print(f"FALSE BLOCK = {false_block}")
if false_block:
    failures.append(f"{false_block} false block(s) among non-faulted services")
print(f"  unverified observations across all episodes: {unverified_total}")

if failures:
    print("FAILURES:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("all T+30 assertions hold: cliffs blocked by verified counterexamples, "
      "healthy control unblocked, all evidence signed")
EOF

echo "== waiting for the scaled 24h outcome horizon"
HORIZON_S=$(SCALE="$SCALE" python3 -c \
  'import os; print(int(86400 * float(os.environ["SCALE"]) + 900))')
DEADLINE=$(( $(date +%s) + HORIZON_S ))
while :; do
  labeled=$(INTEL="$INTEL" T_START="$T_START" python3 -c "
import json, os, urllib.request
NAMES = {'demo-leak', 'demo-retry', 'demo-cred'}
eps = json.load(urllib.request.urlopen(os.environ['INTEL'] + '/intel/episodes?status=closed'))
print(len([e for e in eps
           if not e['episode_id'].startswith('fx_')
           and e['started_at'] >= os.environ['T_START']
           and e['service_uid'].split('/')[-3] in NAMES
           and e.get('final_label')]))")
  [ "$labeled" -ge 3 ] && break
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "FAIL: outcome horizon timed out after ${HORIZON_S}s ($labeled/3 labeled)"
    exit 1
  fi
  sleep 15
done

echo "== delayed-regression ground truth"
INTEL="$INTEL" T_START="$T_START" python3 - <<'EOF'
import json, os, sys, urllib.request
INTEL = os.environ["INTEL"]
T_START = os.environ["T_START"]
NAMES = ("demo-leak", "demo-retry", "demo-cred")
eps = json.load(urllib.request.urlopen(f"{INTEL}/intel/episodes?status=closed"))
by_service = {}
for e in eps:
    if e["episode_id"].startswith("fx_") or e["started_at"] < T_START:
        continue
    by_service.setdefault(e["service_uid"].split("/")[-3], e)
recall = 0
for name in NAMES:
    label = by_service.get(name, {}).get("final_label")
    print(f"  {name:12s} final_label={label}")
    recall += label == "regressed"
print(f"delayed-regression recall {recall}/3")
sys.exit(0 if recall == 3 else 1)
EOF
echo "FF GOLDEN GREEN"
