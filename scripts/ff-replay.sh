#!/usr/bin/env bash
# Fast-Forward determinism golden: the same seeded world, the same deploy,
# the same budget MUST yield byte-identical temporal findings. Runs the
# demo-leak cycle twice — world reset (seed 42) + FF replay reset each
# time — and compares canonical captures of {hazard ids, counterexample
# template, event-sequence digest, first_divergence_age}. Ids that are
# per-run by construction (episode_id, request_id, cx_id) are excluded;
# everything the determinism contract covers is compared verbatim.
#
# Requires up: gcp_sim (7620/7621), probe target (7640), gcp-observe sim
# mode (7600/7601), rollout-intel (7610/7611), fastforward (7630/7631,
# FF_MODE=full), relay (files the FF request on deploy), runtime worker,
# and an autocloud-tenant ENSEMBLE_TOKEN exported.
set -euo pipefail
cd "$(dirname "$0")"
WORLD="${WORLD_API:-http://127.0.0.1:7621}"
INTEL="${INTEL_API:-http://127.0.0.1:7611}"
FF="${FF_API:-http://127.0.0.1:7631}"

capture_once() {  # progress on stderr; the canonical capture JSON on stdout
  echo "  resetting world (seed 42) + fastforward replay state" >&2
  curl -sf -X POST "$WORLD/world/reset" -d '{"seed":42}' > /dev/null
  curl -sf -X POST "$FF/ff/replay/reset" -d '{}' > /dev/null
  sleep 5   # the relay tracks the feed by length; let it see the emptied feed

  local t_start
  t_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  curl -s -X POST "$WORLD/world/deploy" -d '{"service":"demo-leak"}' > /dev/null
  echo "  deployed demo-leak; waiting for its episode" >&2

  local ep=""
  for _ in $(seq 1 60); do
    ep=$(INTEL="$INTEL" T_START="$t_start" python3 -c "
import json, os, urllib.request
eps = json.load(urllib.request.urlopen(os.environ['INTEL'] + '/intel/episodes'))
m = [e for e in eps if not e['episode_id'].startswith('fx_')
     and e['started_at'] >= os.environ['T_START']
     and e['service_uid'].split('/')[-3] == 'demo-leak']
print(m[0]['episode_id'] if m else '')")
    [ -n "$ep" ] && break
    sleep 2
  done
  [ -n "$ep" ] || { echo "FAIL: no demo-leak episode appeared" >&2; return 1; }

  echo "  episode $ep; waiting for the FF terminal packet" >&2
  local envs="{}" n=0
  for _ in $(seq 1 150); do
    envs=$(curl -s "$FF/ff/episodes/$ep/result-envelopes")
    n=$(printf '%s' "$envs" | python3 -c '
import json, sys
try:
    print(len(json.load(sys.stdin).get("envelopes", []) or []))
except Exception:
    print(0)')
    [ "$n" -gt 0 ] && break
    sleep 2
  done
  [ "$n" -gt 0 ] || { echo "FAIL: FF request for $ep never went terminal" >&2; return 1; }

  printf '%s' "$envs" | FF="$FF" python3 -c '
import hashlib, json, os, sys, urllib.request

def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

envs = json.load(sys.stdin)["envelopes"]
results = [e for e in envs if e.get("type") == "fastforward_result"]
assert results, "no fastforward_result envelope"
payload = results[0]["payload"]
packet = json.load(urllib.request.urlopen(
    os.environ["FF"] + "/ff/requests/" + payload["request_id"]))
cxs = sorted(packet.get("counterexamples") or [],
             key=lambda c: (c.get("hazard_id") or "", c.get("template") or ""))
capture = {
    "hazard_ids": sorted(h["hazard_id"] for h in payload.get("hazards", [])),
    "outcome": payload.get("outcome"),
    "counterexamples": [{
        "hazard_id": c.get("hazard_id"),
        "template": c.get("template"),
        "event_sequence_digest": "sha256:" + hashlib.sha256(
            canonical(c.get("event_sequence")).encode()).hexdigest(),
        "first_divergence_age": c.get("first_divergence_age"),
    } for c in cxs],
}
print(canonical(capture))'
}

echo "== run 1"
CAP1=$(capture_once)
echo "== run 2"
CAP2=$(capture_once)
echo "  capture 1: $CAP1"
echo "  capture 2: $CAP2"
if [ "$CAP1" != "$CAP2" ]; then
  echo "FAIL: captures differ across identical seeded runs"
  exit 1
fi
echo "captures byte-identical across two seeded runs"
echo "PASS"
