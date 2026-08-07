"""Stable behavioral profiles: what the KNOWN-GOOD revision does under the
same probe template, keyed by environment fingerprint.

A profile from a different spec_digest or runtime is silently unusable —
comparing a candidate against a baseline gathered under different behavior
would manufacture divergence. Expiry is enforced at read time.
"""

import hashlib
import json
import time

from .db import now_iso
from .stats import mad_z


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def env_fingerprint(spec: dict) -> dict:
    sd = spec.get("spec_digest")
    if not sd:
        sd = "sd_" + hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return {"spec_digest": sd, "sim_seeded": True, "runtime": "probe-target-v1"}


def compatible(a: dict, b: dict) -> bool:
    return (a.get("runtime") == b.get("runtime")
            and a.get("spec_digest") == b.get("spec_digest"))


def z(value: float, stats: dict, metric: str) -> float:
    """MAD z-score of a candidate value against profile stats {metric:{median,mad,n}}."""
    st = stats[metric]
    return mad_z(value, st["median"], st["mad"])


class ProfileStore:
    def __init__(self, db):
        self._db = db

    def put(self, service: str, template: str, env_fp: dict, stats: dict,
            ttl_days: float = 14) -> str:
        expires_at = _iso(time.time() + ttl_days * 86400)
        return self._db.insert_profile(service, template, env_fp, stats, expires_at)

    def get(self, service: str, template: str, env_fp: dict) -> dict | None:
        row = self._db.find_profile(service, template, env_fp, now_iso())
        return row["stats"] if row else None
