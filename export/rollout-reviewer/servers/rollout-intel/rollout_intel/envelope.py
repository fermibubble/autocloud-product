"""Observation-envelope verification — rollout-intel's side of the contract.

The signing side lives in mcp-servers/gcp/envelope.py; both processes share
OBS_SIGNING_KEY via env. The signed-field set and canonicalization here MUST
match the minting side exactly — this pair of files IS the evidence
contract. An envelope failing any check cannot satisfy a policy rule.
"""

import hashlib
import hmac
import json
import os
import time

_KEY = os.environ.get("OBS_SIGNING_KEY", "dev-observation-key").encode()
_SIGNED_FIELDS = ("observation_id", "type", "scope", "observed_at", "fresh_until", "content_hash")


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _sign(env: dict) -> str:
    basis = {k: env.get(k) for k in _SIGNED_FIELDS}
    return hmac.new(_KEY, _canonical(basis), hashlib.sha256).hexdigest()


def verify(env: dict, now: float | None = None) -> tuple[bool, str]:
    """(ok, reason): signature, payload hash, freshness."""
    try:
        if not hmac.compare_digest(_sign(env), env.get("sig", "")):
            return False, "bad signature"
        payload_hash = "sha256:" + hashlib.sha256(_canonical(env.get("payload"))).hexdigest()
        if payload_hash != env.get("content_hash"):
            return False, "payload hash mismatch"
        now_iso = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time())
        )
        if now_iso > env.get("fresh_until", ""):
            return False, f"stale (fresh_until {env.get('fresh_until')})"
        return True, "ok"
    except Exception as exc:
        return False, f"malformed: {exc}"
