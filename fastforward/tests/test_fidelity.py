"""Fidelity-ledger tests: gates, geometric aggregate, and the sim cap."""

import math

from rollout_fastforward.fidelity import AXES, SIM_STATE_CAP, report

FULL = {"input_shape": 0.8, "concurrency": 0.8, "clock_coverage": 0.8,
        "state_representativeness": 0.5, "dependency_behavior": 0.8,
        "side_effect_semantics": 0.8}


def test_required_axis_gate():
    out = report(FULL, {"input_shape": 0.6})
    assert out["gates_met"]
    out = report(FULL, {"input_shape": 0.9})
    assert not out["gates_met"]


def test_geometric_aggregate():
    out = report(FULL, {})
    expected = math.exp(sum(math.log(v) for v in
                            (0.8, 0.8, 0.8, 0.5, 0.8, 0.8)) / 6)
    assert math.isclose(out["aggregate"], expected, rel_tol=1e-9)


def test_zero_axis_zeroes_aggregate_and_is_unsupported():
    scores = dict(FULL, concurrency=0.0)
    out = report(scores, {})
    assert out["aggregate"] == 0.0
    assert out["unsupported"] == ["concurrency"]


def test_missing_axis_counts_as_zero():
    scores = {a: 0.8 for a in AXES if a != "side_effect_semantics"}
    out = report(scores, {})
    assert out["aggregate"] == 0.0
    assert "side_effect_semantics" in out["unsupported"]


def test_sim_state_cap_applies():
    # The ledger must not overclaim: sim state realism is capped no matter
    # what the caller scores it.
    scores = dict(FULL, state_representativeness=0.95)
    out = report(scores, {})
    assert out["axes"]["state_representativeness"] == SIM_STATE_CAP
    # A gate above the cap is therefore unreachable on sim evidence.
    assert not report(scores, {"state_representativeness": 0.7})["gates_met"]
    assert report(scores, {"state_representativeness": 0.6})["gates_met"]


def test_partial_weights_restrict_aggregate():
    scores = dict(FULL, concurrency=0.0)
    out = report(scores, {}, weights={"input_shape": 1.0, "clock_coverage": 1.0})
    assert math.isclose(out["aggregate"], 0.8, rel_tol=1e-9)
