#!/usr/bin/env bash
# Seed Fast-Forward temporal profiles: one POST /ff/profiles/seed per
# service, over the union of catalog/services.yaml and the seven sim
# fixture services (a stale catalog must never leave a golden service
# unprofiled). Prints the created profiles; any non-200 fails loudly.
#
# Requires up: fastforward REST (:7631, or FF_API).
set -euo pipefail
cd "$(dirname "$0")"
FF="${FF_API:-http://127.0.0.1:7631}"
CATALOG="../catalog/services.yaml"

# PyYAML may be absent from the system python; uv is already the product's
# Python toolchain, so fall back to it (run-suite.sh convention).
PY="python3"
$PY -c "import yaml" 2>/dev/null || PY="uv run --with pyyaml python3"

SERVICES=$($PY - "$CATALOG" <<'EOF'
import sys, yaml
FIXTURES = ["demo-healthy", "demo-latency", "demo-errors", "demo-thin",
            "demo-leak", "demo-retry", "demo-cred"]
try:
    names = [s["name"] for s in yaml.safe_load(open(sys.argv[1]))["services"]]
except Exception:
    names = []
seen = []
for name in names + FIXTURES:
    if name not in seen:
        seen.append(name)
print("\n".join(seen))
EOF
)

echo "== seeding fastforward profiles at $FF"
while IFS= read -r svc; do
  [ -z "$svc" ] && continue
  resp=$(curl -s -w '\n%{http_code}' -X POST "$FF/ff/profiles/seed" \
    -d "{\"service\":\"$svc\"}")
  code=${resp##*$'\n'}
  body=${resp%$'\n'*}
  if [ "$code" != "200" ]; then
    echo "FAIL: seed $svc -> HTTP $code: $body"
    exit 1
  fi
  printf '%s' "$body" | SVC="$svc" python3 -c '
import json, os, sys
profiles = json.load(sys.stdin).get("profiles", [])
print("  " + os.environ["SVC"] + ": " + str(len(profiles)) + " profiles "
      + json.dumps(profiles, separators=(",", ":")))'
done <<< "$SERVICES"
echo "FF PROFILES SEEDED"
