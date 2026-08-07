"""Playbook tests against the in-process sim ProbeWorld: buggy specs are
caught with replayable counterexamples, clean specs stay within envelope,
warm-up never counts as growth, and no playbook passes without a reference."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sim"))

from probe_target import CLEAN_SPEC, ProbeWorld  # noqa: E402

from rollout_fastforward import fidelity, profiles  # noqa: E402
from rollout_fastforward.db import Db  # noqa: E402
from rollout_fastforward.playbooks import credential, leak, retry  # noqa: E402
from rollout_fastforward.probes import ProbeContext  # noqa: E402
from rollout_fastforward.profiles import ProfileStore  # noqa: E402

LEAK_SPEC = {**CLEAN_SPEC, "conn_leak_per_cycle": 3, "handle_threshold": 1000}
RETRY_SPEC = {**CLEAN_SPEC, "retry_p_f": 0.3, "retry_e_k": 4}
CRED_SPEC = {**CLEAN_SPEC, "reuse_after_rotate_bug": True}

HZ_LEAK = {"hazard_id": "hz_leak", "class": "resource_lifecycle", "impact": "high",
           "min_fidelity": {"input_shape": 0.6, "state_representativeness": 0.3}}
HZ_RETRY = {"hazard_id": "hz_retry", "class": "rate_balance", "impact": "high",
            "min_fidelity": {"input_shape": 0.6, "dependency_behavior": 0.5}}
HZ_CRED = {"hazard_id": "hz_cred", "class": "clock_expiry", "impact": "high",
           "min_fidelity": {"clock_coverage": 0.5, "dependency_behavior": 0.5}}


def digest(spec):
    canon = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def ctx_for(spec, hazard, world=None, profiles_store=None, budget=1e9,
            clean=CLEAN_SPEC):
    return ProbeContext(
        target=world or ProbeWorld(), service="demo-x", revision="r2",
        seed=1234, spec=dict(spec), spec_digest=digest(spec),
        request={"request_id": "ffr_t", "manifest_digest": "mf_test1234567890"},
        hazard=hazard, previous_revision="r1",
        clean_spec=dict(clean) if clean else None,
        clean_spec_digest=digest(clean) if clean else "",
        profiles=profiles_store, budget_s=budget)


# --- resource_lifecycle_v1 ---------------------------------------------------


def test_leak_detected_on_buggy_spec():
    res = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK))
    assert res["disposition"] == "counterexample"
    cx = res["counterexample"]
    assert cx["template"] == "resource_lifecycle_v1"
    assert cx["event_sequence"][0]["action"] == "create"
    assert cx["candidate_digest"] == "mf_test1234567890"
    assert cx["state_slice_digest"] == digest(LEAK_SPEC)
    # 3 handles / 100 cycles, divergence at the first post-warmup round.
    assert abs(res["measurements"]["slope_per_cycle"]["slope"] - 0.03) < 1e-9
    assert cx["first_divergence_age"]["cycles"] == 200


def test_leak_clean_spec_within_envelope_and_warmup_excluded():
    res = leak.run(ctx_for(CLEAN_SPEC, HZ_LEAK))
    assert res["disposition"] == "within_envelope"
    # Warm-up excluded: the pool warmed to 10 during warm-up, but every
    # measured point sits at the plateau -> slope exactly 0.
    assert res["measurements"]["slope_per_cycle"]["slope"] == 0.0
    assert all(h == res["measurements"]["points"][0][1]
               for _, h in res["measurements"]["points"])
    assert res["measurements"]["reference"] == "paired_clean"


def test_leak_uses_profile_when_present(tmp_path):
    store = ProfileStore(Db(str(tmp_path / "ff.db")))
    fp = profiles.env_fingerprint({"spec_digest": digest(CLEAN_SPEC)})
    store.put("demo-x", "resource_lifecycle_v1", fp,
              {"slope_per_cycle": {"median": 0.0, "mad": 0.0, "n": 4}})
    world = ProbeWorld()
    res = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK, world=world, profiles_store=store))
    assert res["disposition"] == "counterexample"
    assert res["measurements"]["reference"] == "profile"
    assert world._next == 1  # only the candidate instance; NO paired clean run


def test_leak_without_any_reference_is_inconclusive():
    res = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK, clean=None))
    assert res["disposition"] == "inconclusive"
    assert res["stop_reason"] == "no_reference"


def test_leak_zero_budget_is_inconclusive_budget():
    res = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK, budget=0))
    assert res["disposition"] == "inconclusive"
    assert res["stop_reason"] == "inconclusive_budget"


def test_leak_fidelity_axes_and_effect_accounting():
    res = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK))
    axes = res["fidelity_axes"]
    assert axes["input_shape"] == 0.7 and axes["concurrency"] == 0.6
    assert axes["clock_coverage"] == 0.5  # inventory says partial
    assert axes["state_representativeness"] == fidelity.SIM_STATE_CAP
    assert axes["dependency_behavior"] == 0.8
    assert axes["side_effect_semantics"] == 1.0
    assert res["measurements"]["side_effect_attempts"] > 0  # observed, contained
    assert res["fidelity_report"]["gates_met"]


# --- rate_balance_v1 ---------------------------------------------------------


def test_retry_amplification_detected():
    res = retry.run(ctx_for(RETRY_SPEC, HZ_RETRY))
    assert res["disposition"] == "counterexample"
    m = res["measurements"]
    assert abs(m["m"] - 1.2) < 0.01  # observed failure->retry branching
    assert m["queue_slope_per_request"]["lo"] > 0
    assert res["counterexample"]["first_divergence_age"]["requests"] == 100


def test_retry_clean_spec_within_envelope():
    res = retry.run(ctx_for(CLEAN_SPEC, HZ_RETRY))
    assert res["disposition"] == "within_envelope"
    m = res["measurements"]
    assert m["m"] < 1
    assert m["queue_slope_per_request"]["hi"] < retry.SAFE_QUEUE_SLOPE


def test_retry_without_reference_is_inconclusive():
    res = retry.run(ctx_for(RETRY_SPEC, HZ_RETRY, clean=None))
    assert res["disposition"] == "inconclusive"
    assert res["stop_reason"] == "no_reference"


# --- cred_lifecycle_v1 -------------------------------------------------------


def test_cred_stale_reuse_diverges_at_the_right_event():
    res = credential.run(ctx_for(CRED_SPEC, HZ_CRED))
    assert res["disposition"] == "counterexample"
    cx = res["counterexample"]
    age = cx["first_divergence_age"]
    # Divergence exactly at the first post-rotation, post-expiry batch.
    assert age["rotations"] == 1
    assert age["cred_age_s"] == CRED_SPEC["cred_ttl_s"] + credential.ADVANCE_SLACK_S
    assert age["cycles"] == credential.WARM_CYCLES
    assert res["measurements"]["stale_reuse_count"] > 0


def test_cred_clean_spec_recovers_through_transient_fault():
    res = credential.run(ctx_for(CLEAN_SPEC, HZ_CRED))
    assert res["disposition"] == "within_envelope"
    m = res["measurements"]
    assert m["stale_reuse_count"] == 0
    assert m["refresh_failures"] == 1  # the armed transient, then recovery
    assert m["counters"]["cred_age_s"] == 0  # re-authenticated
    assert m["counters"]["failures"] == 0


def test_cred_axes_stay_honest_about_clock_coverage():
    res = credential.run(ctx_for(CRED_SPEC, HZ_CRED))
    # The expiry axis was advanced explicitly (0.9), but the general clock
    # axis reports the honest inventory value.
    assert res["measurements"]["expiry_axis_coverage"] == 0.9
    assert res["fidelity_axes"]["clock_coverage"] == 0.5
    assert res["fidelity_report"]["gates_met"]


def test_cred_zero_budget_is_inconclusive_budget():
    res = credential.run(ctx_for(CRED_SPEC, HZ_CRED, budget=0))
    assert res["disposition"] == "inconclusive"
    assert res["stop_reason"] == "inconclusive_budget"


# --- determinism across playbooks -------------------------------------------


def test_same_seed_same_measurements():
    a = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK))
    b = leak.run(ctx_for(LEAK_SPEC, HZ_LEAK))
    assert a["measurements"]["points"] == b["measurements"]["points"]
    assert a["counterexample"] == b["counterexample"]
