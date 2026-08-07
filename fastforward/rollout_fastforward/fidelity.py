"""Fidelity ledger: how much the probe world resembles production.

The ledger must not overclaim: the sim probe target is spec-driven, so
state representativeness is structurally capped at SIM_STATE_CAP no matter
what a caller scores it — a hazard whose gate needs more than the cap can
never report gates_met on sim evidence.
"""

import math

AXES = ("input_shape", "concurrency", "clock_coverage",
        "state_representativeness", "dependency_behavior", "side_effect_semantics")

SIM_STATE_CAP = 0.6


def report(axis_scores: dict, required: dict, weights: dict | None = None) -> dict:
    """{"axes","aggregate","gates_met","unsupported"}. Aggregate is the
    weighted geometric mean over AXES (a 0.0 axis zeroes it); required maps
    axis -> minimum score; missing axes score 0.0."""
    scores = {}
    for axis in AXES:
        s = float(axis_scores.get(axis, 0.0))
        if axis == "state_representativeness":
            s = min(s, SIM_STATE_CAP)
        scores[axis] = s
    unsupported = [a for a in AXES if scores[a] <= 0.0]
    w = weights if weights is not None else {a: 1.0 for a in AXES}
    active = [a for a in AXES if w.get(a, 0.0) > 0]
    total = sum(w[a] for a in active)
    if not active or any(scores[a] <= 0.0 for a in active):
        aggregate = 0.0
    else:
        aggregate = math.exp(sum(w[a] * math.log(scores[a]) for a in active) / total)
    gates_met = all(scores.get(a, 0.0) >= m for a, m in (required or {}).items())
    return {"axes": scores, "aggregate": aggregate,
            "gates_met": gates_met, "unsupported": unsupported}
