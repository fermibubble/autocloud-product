"""Stable-profile tests: expiry and fingerprint mismatch return None."""

import math

from rollout_fastforward import profiles
from rollout_fastforward.db import Db

SPEC = {"service": "demo-leak", "revision": "r1", "spec": {"lifecycle": {}},
        "spec_digest": "sd_abc123"}
STATS = {"open_handles": {"median": 10.0, "mad": 2.0, "n": 50}}


def make_store(tmp_path):
    return profiles.ProfileStore(Db(str(tmp_path / "ff.db")))


def test_env_fingerprint_shape():
    fp = profiles.env_fingerprint(SPEC)
    assert fp == {"spec_digest": "sd_abc123", "sim_seeded": True,
                  "runtime": "probe-target-v1"}


def test_put_get_roundtrip(tmp_path):
    store = make_store(tmp_path)
    fp = profiles.env_fingerprint(SPEC)
    store.put("demo-leak", "resource_lifecycle_v1", fp, STATS)
    assert store.get("demo-leak", "resource_lifecycle_v1", fp) == STATS


def test_expired_profile_returns_none(tmp_path):
    store = make_store(tmp_path)
    fp = profiles.env_fingerprint(SPEC)
    store.put("demo-leak", "resource_lifecycle_v1", fp, STATS, ttl_days=-1)
    assert store.get("demo-leak", "resource_lifecycle_v1", fp) is None


def test_fingerprint_mismatch_returns_none(tmp_path):
    store = make_store(tmp_path)
    store.put("demo-leak", "resource_lifecycle_v1",
              profiles.env_fingerprint(SPEC), STATS)
    other = profiles.env_fingerprint(dict(SPEC, spec_digest="sd_zzz999"))
    assert store.get("demo-leak", "resource_lifecycle_v1", other) is None


def test_compatible_ignores_extras():
    a = {"spec_digest": "sd_1", "runtime": "probe-target-v1", "sim_seeded": True}
    b = {"spec_digest": "sd_1", "runtime": "probe-target-v1", "sim_seeded": False}
    assert profiles.compatible(a, b)
    assert not profiles.compatible(a, dict(b, runtime="prod"))


def test_z_math():
    # value = median + 3 * 1.4826 * mad -> z of 3.
    value = 10.0 + 3 * 1.4826 * 2.0
    assert math.isclose(profiles.z(value, STATS, "open_handles"), 3.0, rel_tol=1e-9)
    assert profiles.z(10.0, STATS, "open_handles") == 0.0
