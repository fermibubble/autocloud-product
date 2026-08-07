#!/usr/bin/env bash
# Start (or stop) the rollout-reviewer tool surface, self-contained.
#
#   ./scripts/run-stack.sh          start sim + gcp-observe + rollout-intel
#   ./scripts/run-stack.sh stop     stop whatever this script started
#   LIVE_GCP=1 ./scripts/run-stack.sh   skip the sim; gcp-observe talks to
#                                       real Google endpoints (needs ADC +
#                                       GCP_PROJECT)
#
# Ports: sim :7620 (GCP API) / :7621 (world) - gcp-observe :7600 (MCP) /
# :7601 (bundle) - rollout-intel :7610 (MCP) / :7611 (REST).
# State: run/episode-store.db (override with INTEL_DB). Logs: run/*.log.
# OBS_SIGNING_KEY: both servers default to the shared dev key; in
# production export the SAME non-default value to BOTH processes.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
RUN="$ROOT/run"
mkdir -p "$RUN"
PIDFILE="$RUN/stack.pids"

if [[ "${1:-}" == "stop" ]]; then
  [[ -f "$PIDFILE" ]] && kill $(cat "$PIDFILE") 2>/dev/null || true
  rm -f "$PIDFILE"
  echo "stack stopped"
  exit 0
fi

if [[ -f "$PIDFILE" ]] && kill -0 $(head -1 "$PIDFILE") 2>/dev/null; then
  echo "stack already running (pids: $(tr '\n' ' ' < "$PIDFILE"))"
  exit 0
fi
: > "$PIDFILE"

if [[ "${LIVE_GCP:-}" != "1" ]]; then
  python3 "$ROOT/sim/gcp_sim.py" --seed "${SIM_SEED:-42}" > "$RUN/sim.log" 2>&1 &
  echo $! >> "$PIDFILE"
fi

(
  cd "$ROOT/servers/gcp-observe"
  if [[ "${LIVE_GCP:-}" == "1" ]]; then
    GCP_PROJECT="${GCP_PROJECT:?set GCP_PROJECT for LIVE_GCP=1}" \
      uv run --project . python server.py --port 7600 > "$RUN/observe.log" 2>&1 &
  else
    GCP_PROJECT="${GCP_PROJECT:-sim-project}" \
    GCP_API_BASE="http://127.0.0.1:7620" GCP_NO_AUTH=1 \
      uv run --project . python server.py --port 7600 > "$RUN/observe.log" 2>&1 &
  fi
  echo $! >> "$PIDFILE"
)

(
  cd "$ROOT/servers/rollout-intel"
  INTEL_DB="${INTEL_DB:-$RUN/episode-store.db}" \
    uv run --project . python -m rollout_intel.service \
      --mcp-port 7610 --rest-port 7611 \
      --policy policies/rollout-slo.yaml --catalog catalog/services.yaml \
      > "$RUN/intel.log" 2>&1 &
  echo $! >> "$PIDFILE"
)

echo -n "waiting for health"
for _ in $(seq 1 30); do
  ok=1
  curl -sf -m 1 "http://127.0.0.1:7611/intel/health" > /dev/null 2>&1 || ok=0
  curl -sf -m 1 "http://127.0.0.1:7601/observe/bundle?service=demo-healthy&stage=T%2B5" > /dev/null 2>&1 || ok=0
  if [[ "${LIVE_GCP:-}" != "1" ]]; then
    curl -sf -m 1 "http://127.0.0.1:7621/world/services" > /dev/null 2>&1 || ok=0
  fi
  [[ $ok == 1 ]] && { echo " - up"; exit 0; }
  echo -n "."
  sleep 1
done
echo " - FAILED (see run/*.log)"
exit 1
