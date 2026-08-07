"""Replay tests: the determinism contract makes counterexamples proofs —
same seed+spec+sequence reproduces the identical divergence, and any
tampering with the event sequence fails verification."""

import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sim"))

from probe_target import CLEAN_SPEC, ProbeWorld  # noqa: E402

from rollout_fastforward import counterexample  # noqa: E402
from rollout_fastforward.db import Db  # noqa: E402
from rollout_fastforward.playbooks import credential, leak  # noqa: E402
from rollout_fastforward.probes import ProbeContext  # noqa: E402

LEAK_SPEC = {**CLEAN_SPEC, "conn_leak_per_cycle": 3, "handle_threshold": 1000}
CRED_SPEC = {**CLEAN_SPEC, "reuse_after_rotate_bug": True}

HZ_LEAK = {"hazard_id": "hz_leak", "class": "resource_lifecycle", "impact": "high",
           "min_fidelity": {"input_shape": 0.6, "state_representativeness": 0.3}}
HZ_CRED = {"hazard_id": "hz_cred", "class": "clock_expiry", "impact": "high",
           "min_fidelity": {"clock_coverage": 0.5, "dependency_behavior": 0.5}}


def digest(spec):
    canon = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def ctx_for(spec, hazard):
    return ProbeContext(
        target=ProbeWorld(), service="demo-x", revision="r2", seed=1234,
        spec=dict(spec), spec_digest=digest(spec),
        request={"request_id": "ffr_t", "manifest_digest": "mf_test1234567890"},
        hazard=hazard, previous_revision="r1",
        clean_spec=dict(CLEAN_SPEC), clean_spec_digest=digest(CLEAN_SPEC),
        profiles=None, budget_s=1e9)


def leak_cx():
    return leak.run(ctx_for(LEAK_SPEC, HZ_LEAK))["counterexample"]


def cred_cx():
    return credential.run(ctx_for(CRED_SPEC, HZ_CRED))["counterexample"]


def test_cx_id_is_deterministic():
    a, b = leak_cx(), leak_cx()
    assert a["cx_id"] == b["cx_id"]
    assert a["cx_id"].startswith("cx_") and len(a["cx_id"]) == 15
    assert a == b  # whole artifact, event digest included


def test_leak_replay_verifies_on_fresh_world():
    cx = leak_cx()
    verified, observed = counterexample.replay(cx, ProbeWorld())
    assert verified
    assert observed["first_divergence_age"] == cx["first_divergence_age"]
    assert observed["events_digest"] == cx["observed_candidate"]["events_digest"]


def test_cred_replay_verifies_on_fresh_world():
    cx = cred_cx()
    verified, observed = counterexample.replay(cx, ProbeWorld())
    assert verified
    assert observed["first_divergence_age"]["rotations"] == 1
    assert observed["first_divergence_age"] == cx["first_divergence_age"]


def test_tampered_event_sequence_fails_replay():
    cx = leak_cx()
    tampered = copy.deepcopy(cx)
    tampered["event_sequence"][1]["args"]["n"] = 999  # inflate the warm-up
    verified, _ = counterexample.replay(tampered, ProbeWorld())
    assert not verified


def test_tampered_seed_fails_replay():
    cx = cred_cx()
    tampered = copy.deepcopy(cx)
    tampered["event_sequence"][0]["args"]["seed"] = 999
    # Same events for this deterministic sequence... but the digest guards
    # the claimed age too: forge the age and replay must refuse.
    tampered2 = copy.deepcopy(cx)
    tampered2["first_divergence_age"] = dict(cx["first_divergence_age"],
                                             cred_age_s=1)
    verified, _ = counterexample.replay(tampered2, ProbeWorld())
    assert not verified


def test_dropped_action_fails_replay():
    cx = cred_cx()
    tampered = copy.deepcopy(cx)
    # Drop the rotate_key: without rotation there is no stale reuse.
    tampered["event_sequence"] = [a for a in tampered["event_sequence"]
                                  if a["action"] != "rotate_key"]
    verified, observed = counterexample.replay(tampered, ProbeWorld())
    assert not verified
    assert observed["first_divergence_age"] is None  # divergence never recurs


def test_db_roundtrip_and_mark_verified(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    cx = leak_cx()
    db.insert_counterexample("ffr_t", cx)
    loaded = db.get_counterexample(cx["cx_id"])
    assert loaded["event_sequence"] == cx["event_sequence"]
    assert loaded["replay_verified"] is False
    verified, observed = counterexample.replay(loaded, ProbeWorld())
    assert verified
    db.mark_replay_verified(cx["cx_id"], observed["first_divergence_age"])
    assert db.get_counterexample(cx["cx_id"])["replay_verified"] is True
