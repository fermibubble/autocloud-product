#!/bin/bash
# Wrapper entrypoint: start the trustworthy rollout reviewer stack, then
# hand off to the harness's original entrypoint unchanged.
#
# Env knobs (all optional):
#   LIVE_GCP=1        gcp-observe talks to real Google APIs (container ADC);
#                     the sim is not started
#   GCP_PROJECT       required when LIVE_GCP=1
#   OBS_SIGNING_KEY   set the SAME value for both server processes in
#                     production (dev default otherwise)
#   INTEL_DB          episode store path (default below keeps it on the
#                     /workspace volume so episodes survive restarts)
set -e

export INTEL_DB="${INTEL_DB:-/workspace/rollout-reviewer-run/episode-store.db}"
mkdir -p "$(dirname "$INTEL_DB")"

echo "Starting trustworthy rollout reviewer stack..."
/opt/rollout-reviewer/scripts/run-stack.sh

echo "Reviewer stack up: rollout-intel :7610(mcp)/:7611(rest), gcp-observe :7600(mcp)/:7601(bundle)$( [[ "${LIVE_GCP:-}" == "1" ]] || echo ", sim :7620/:7621" )"

# Hand off to the original harness entrypoint (Chrome + mcp-proxy).
exec /usr/local/bin/entrypoint_sandbox.sh
