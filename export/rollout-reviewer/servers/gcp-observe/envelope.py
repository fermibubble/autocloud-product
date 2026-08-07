"""Signed observation envelopes — the unit of policy-grade evidence.

Every gcp-observe tool result is wrapped here and HMAC-signed with
OBS_SIGNING_KEY (shared only with rollout-intel; never in a sandbox or a
prompt). The agent carries envelopes verbatim into evaluate_policy /
record_checkpoint; rollout-intel re-verifies signature, content hash, and
freshness. An unverifiable observation cannot satisfy any policy rule —
fabricating or editing evidence yields insufficient_evidence, not a wrong
verdict.
"""

import hashlib
import hmac
import json
import os
import time
import uuid

_KEY = os.environ.get("OBS_SIGNING_KEY", "dev-observation-key").encode()

# Signature covers the identity+integrity fields, not the (hashed) payload
# bytes themselves.
_SIGNED_FIELDS = ("observation_id", "type", "scope", "observed_at", "fresh_until", "content_hash")


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def sign(envelope: dict) -> str:
    basis = {k: envelope.get(k) for k in _SIGNED_FIELDS}
    return hmac.new(_KEY, _canonical(basis), hashlib.sha256).hexdigest()


def mint(obs_type: str, scope: dict, payload, quality: dict | None = None,
         source: str = "gcp-observe", ttl_seconds: int = 600) -> dict:
    now = time.time()
    envelope = {
        "observation_id": f"obs-{uuid.uuid4().hex[:12]}",
        "type": obs_type,
        "scope": scope,
        "observed_at": _iso(now),
        "fresh_until": _iso(now + ttl_seconds),
        "source": source,
        "payload": payload,
        "quality": quality or {"completeness": "COMPLETE"},
        "content_hash": "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    envelope["sig"] = sign(envelope)
    return envelope


def verify(envelope: dict, now: float | None = None) -> tuple[bool, str]:
    """(ok, reason). Checks signature, payload hash, and freshness."""
    try:
        expected = sign(envelope)
        if not hmac.compare_digest(expected, envelope.get("sig", "")):
            return False, "bad signature"
        payload_hash = "sha256:" + hashlib.sha256(_canonical(envelope.get("payload"))).hexdigest()
        if payload_hash != envelope.get("content_hash"):
            return False, "payload hash mismatch"
        fresh_until = envelope.get("fresh_until", "")
        now_iso = _iso(now if now is not None else time.time())
        if now_iso > fresh_until:
            return False, f"stale (fresh_until {fresh_until})"
        return True, "ok"
    except Exception as exc:  # malformed envelope shapes land here
        return False, f"malformed: {exc}"
