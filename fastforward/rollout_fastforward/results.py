"""Decision assembly: hazard dispositions -> outcome, signed envelopes,
one-shot snapshot, terminal state.

The precedence is the safety order: a counterexample outranks starvation,
starvation outranks incapability, and neither inconclusive_budget nor
unsupported_temporal_risk can EVER become a pass — they terminate in
BUDGET_EXHAUSTED / UNSUPPORTED, and policy v2 maps both to insufficient.
degrade() is the worker's only exception landing zone: any crash mid-run
mints an unsupported envelope rather than silence.
"""

import json

from . import envelope
from . import inventory as _inventory
from .fidelity import AXES
from .states import TERMINAL

OUTCOME_STATE = {
    "temporal_counterexample": "COUNTEREXAMPLE",
    "inconclusive_budget": "BUDGET_EXHAUSTED",
    "unsupported_temporal_risk": "UNSUPPORTED",
    "no_material_temporal_hazard": "COMPLETED",
    "projected_boundary": "COMPLETED",
    "bounded_future_envelope": "COMPLETED",
}

_BUDGET_D = frozenset({"inconclusive_budget"})
_UNSUP_D = frozenset({"unsupported", "inconclusive"})
_WITHIN_D = frozenset({"within_envelope", "bounded_within_envelope"})

# Contract shape of a counterexample envelope payload — no db bookkeeping.
_CX_KEYS = ("cx_id", "hazard_id", "candidate_digest", "template",
            "state_slice_digest", "event_sequence", "expected_stable",
            "observed_candidate", "first_divergence_age", "replay_seed",
            "replay_verified")


def combine_fidelity(reports: list[dict]) -> dict:
    """Conservative merge: per-axis minimum, all gates must hold."""
    if not reports:
        return {}
    return {"axes": {a: min(r["axes"].get(a, 0.0) for r in reports) for a in AXES},
            "aggregate": min(r["aggregate"] for r in reports),
            "gates_met": all(r["gates_met"] for r in reports),
            "unsupported": sorted({u for r in reports for u in r["unsupported"]})}


def decide_outcome(dispositions: list[dict], fidelity_reports: list[dict]) -> str:
    ds = [d["disposition"] for d in dispositions]
    if "counterexample" in ds:
        return "temporal_counterexample"
    if any(d in _BUDGET_D for d in ds):
        return "inconclusive_budget"
    if any(d in _UNSUP_D or d not in _WITHIN_D | {"projected_boundary"}
           for d in ds):
        return "unsupported_temporal_risk"
    if not ds:
        return "no_material_temporal_hazard"
    if "projected_boundary" in ds:
        return "projected_boundary"
    # All within-envelope: a clean bill REQUIRES every fidelity gate met —
    # otherwise the honest claim is only a projected boundary.
    if all(r.get("gates_met") for r in fidelity_reports):
        return "bounded_future_envelope"
    return "projected_boundary"


def _scope(request: dict) -> dict:
    return {"service": request["service"], "episode_id": request["episode_id"],
            "stage": "T+30"}


def _ttl(request: dict) -> int:
    # Outlives the checkpoint deadline by a day.
    return int(float(request["deadline_s"] or 0)) + 86400


def finalize(db, request: dict, hazard_dispositions: list[dict],
             fidelity_reports: list[dict], budget_spent, *,
             plan_digest: str = "", mode: str = "full", seed=None,
             profile_ids=(), counterexamples=()) -> dict:
    """Terminal transition for a request that ran to ANALYZING. Mints the
    fastforward_result envelope (+ one temporal_counterexample envelope per
    cx), writes the decision-time snapshot exactly once, then moves to the
    terminal state (stamping decided_at)."""
    request_id, episode_id = request["request_id"], request["episode_id"]
    outcome = decide_outcome(hazard_dispositions, fidelity_reports)
    state = OUTCOME_STATE[outcome]
    granted = json.loads(request["budget_json"] or "{}")
    cx_list = [dict(cx) for cx in counterexamples]
    payload = {
        "outcome": outcome, "request_id": request_id, "episode_id": episode_id,
        "service": request["service"],
        "hazards": [{"hazard_id": d.get("hazard_id"), "class": d.get("class"),
                     "disposition": d.get("disposition"), "mode": d.get("mode")}
                    for d in hazard_dispositions],
        "fidelity": combine_fidelity(fidelity_reports),
        "budget": {"granted": granted, "spent": budget_spent},
        "plan_digest": plan_digest,
        "counterexample_ids": [cx["cx_id"] for cx in cx_list],
    }
    env = envelope.mint("fastforward_result", _scope(request), payload,
                        ttl_seconds=_ttl(request))
    db.set_outcome(request_id, outcome)
    db.insert_envelope(request_id, episode_id, env)
    for cx in cx_list:
        cx_payload = {k: cx.get(k) for k in _CX_KEYS}
        db.insert_envelope(request_id, episode_id,
                           envelope.mint("temporal_counterexample",
                                         _scope(request), cx_payload,
                                         ttl_seconds=_ttl(request)))
    db.write_snapshot_once(request_id, {
        "manifest_digest": request["manifest_digest"], "policy_context": None,
        "profile_ids": list(profile_ids),
        "inventory": _inventory.capabilities(), "seed": seed,
        "plan_digest": plan_digest, "mode": mode})
    db.set_state(request_id, state)
    return {"outcome": outcome, "state": state, "envelope": env}


def degrade(db, request, reason: str) -> dict | None:
    """From ANY non-terminal state: outcome unsupported_temporal_risk,
    state UNSUPPORTED, with a signed envelope carrying the reason. Every
    exception path in the worker lands here; degrade itself must not raise
    and never touches an already-terminal request."""
    try:
        request_id = request["request_id"] if isinstance(request, dict) else request
        row = db.get_request(request_id)
        if row is None or row["state"] in TERMINAL:
            return row
        outcome = "unsupported_temporal_risk"
        hazards = [{"hazard_id": h["hazard_id"], "class": h["class"],
                    "disposition": "unsupported", "mode": None}
                   for h in db.hazards_for(request_id)]
        payload = {
            "outcome": outcome, "request_id": request_id,
            "episode_id": row["episode_id"], "service": row["service"],
            "hazards": hazards, "fidelity": {},
            "budget": {"granted": json.loads(row["budget_json"] or "{}"),
                       "spent": None},
            "plan_digest": "", "counterexample_ids": [],
            "reason": str(reason)[:500],
        }
        env = envelope.mint("fastforward_result", _scope(row), payload,
                            ttl_seconds=_ttl(row))
        db.set_outcome(request_id, outcome)
        db.insert_envelope(request_id, row["episode_id"], env)
        try:
            db.write_snapshot_once(request_id, {
                "manifest_digest": row["manifest_digest"],
                "policy_context": None, "profile_ids": [],
                "inventory": _inventory.capabilities(), "seed": None,
                "plan_digest": "", "mode": "degraded",
                "degraded_reason": str(reason)[:500]})
        except ValueError:
            pass  # snapshot already written by a partial finalize
        db.set_state(request_id, "UNSUPPORTED")
        return db.get_request(request_id)
    except Exception:
        return None
