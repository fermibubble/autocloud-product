#!/usr/bin/env bash
# Seed the fixture services' operational dossiers through the SAME
# governed path a human operator uses: propose (with epistemic type and
# provenance) then promote. Promotion is what activates a revision and
# projects it into the harness store memstore://project/rollout-dossiers.
set -euo pipefail
cd "$(dirname "$0")"
CTL="python3 intelctl.py"

seed() { # service field value type rationale
  rev=$($CTL propose --service "$1" --field "$2" --value "$3" --type "$4" \
        --rationale "$5" | python3 -c 'import json,sys; print(json.load(sys.stdin)["rev_id"])')
  $CTL promote "$rev" --by seed-script > /dev/null
  echo "  $1.$2 = $3 ($4) [$rev]"
}

echo "== seeding dossiers"
seed demo-healthy p99_baseline_ms 185 observed "sim world baseline, seed 42"
seed demo-healthy stabilization_window_minutes 15 observed "traffic stabilizes by T+15 across seeded ladders"
seed demo-healthy traffic_profile '"steady"' approved "catalog: steady synthetic load"
seed demo-latency p99_baseline_ms 185 observed "same baseline family as demo-healthy"
seed demo-errors error_rate_baseline 0.001 observed "sim world healthy error floor"
seed demo-thin traffic_profile '"thin"' approved "catalog: sub-1rps fixture — early stages will be insufficient-evidence by design"
seed demo-thin stabilization_window_minutes 30 asserted "thin traffic needs the full ladder before verdicts firm up"
echo "== done; active claims now project to memstore://project/rollout-dossiers"
