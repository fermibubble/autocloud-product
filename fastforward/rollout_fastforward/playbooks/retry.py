"""rate_balance_v1: does the retry policy amplify failures unboundedly?

Dial a dependency failure rate, then watch two things: the observed
failure->retry branching m (m >= 1 means each failure spawns at least one
retry — self-amplifying) and the queue-depth drift. Fail only when BOTH
hold: m >= 1 and the queue slope's CI floor is above zero.
"""

from .. import counterexample, fidelity, profiles, stopping
from ..probes import BudgetExceeded, ProbeSession
from ..stats import mad, retry_m, theil_sen
from . import base_axes, median

TEMPLATE = "rate_balance_v1"
FAILURE_RATE = 0.2
ROUND_REQUESTS = 100
CONCURRENCY = 8
MAX_ROUNDS = 8
MIN_POINTS = 4
SAFE_QUEUE_SLOPE = 0.05  # per request: anything below this drains
Z_DIVERGE = 3.0


def _baseline(ctx):
    if ctx.profiles is not None and ctx.clean_spec_digest:
        fp = profiles.env_fingerprint({"spec_digest": ctx.clean_spec_digest})
        st = ctx.profiles.get(ctx.service, TEMPLATE, fp)
        if st and "queue_delta_per_round" in st:
            return st, "profile"
    if ctx.clean_spec is None:
        return None, "none"
    s = ProbeSession(ctx.target, ctx.budget_s, ctx.deadline_at)
    try:
        s.create(ctx.service, ctx.previous_revision or "baseline",
                 ctx.seed, ctx.clean_spec)
        s.dependency(FAILURE_RATE, 0)
        prev = s.counters()["queue_depth"]
        deltas = []
        for _ in range(MIN_POINTS):
            s.requests(ROUND_REQUESTS, CONCURRENCY)
            cur = s.counters()["queue_depth"]
            deltas.append(float(cur - prev))
            prev = cur
    finally:
        s.destroy()
    return {"queue_delta_per_round": {"median": median(deltas),
                                      "mad": mad(deltas),
                                      "n": len(deltas)}}, "paired_clean"


def run(ctx) -> dict:
    try:
        baseline, ref_source = _baseline(ctx)
    except BudgetExceeded as exc:
        return {"disposition": "inconclusive", "stop_reason": "inconclusive_budget",
                "measurements": {"error": str(exc)}, "fidelity_axes": {},
                "fidelity_report": fidelity.report({}, ctx.hazard.get("min_fidelity", {}))}
    if baseline is None:
        return {"disposition": "inconclusive", "stop_reason": "no_reference",
                "measurements": {"reference": "none"}, "fidelity_axes": {},
                "fidelity_report": fidelity.report({}, ctx.hazard.get("min_fidelity", {}))}

    session = ProbeSession(ctx.target, ctx.budget_s, ctx.deadline_at)
    points, zs, divergence = [], [], None
    ts = {"slope": 0.0, "lo": 0.0, "hi": 0.0}
    m = 0.0
    decision, stop_reason = "continue", "max_rounds"
    try:
        session.create(ctx.service, ctx.revision, ctx.seed, ctx.spec)
        session.dependency(FAILURE_RATE, 0)
        fid = fidelity.report(base_axes(0), ctx.hazard.get("min_fidelity", {}))
        prev_q = session.counters()["queue_depth"]
        for rnd in range(MAX_ROUNDS):
            session.requests(ROUND_REQUESTS, CONCURRENCY)
            c = session.counters()
            points.append((c["requests"], float(c["queue_depth"])))
            delta = float(c["queue_depth"] - prev_q)
            prev_q = c["queue_depth"]
            zval = profiles.z(delta, baseline, "queue_delta_per_round")
            zs.append(zval)
            if divergence is None and zval > Z_DIVERGE:
                ev = session.events()[-1]  # this round's requests event
                divergence = {"age": ev["age"], "seq": ev["seq"], "round": rnd}
            # Observed branching: each failure spawned retries/failures
            # retries — the e_k folded into the observed ratio.
            m = retry_m(c["retries"] / c["failures"], 1.0) if c["failures"] else 0.0
            if len(points) < MIN_POINTS:
                continue
            ts = theil_sen(points)
            harm_slope = 0.0 if m >= 1 else float("inf")
            decision = stopping.decide(ts["lo"], ts["hi"], harm_slope,
                                       SAFE_QUEUE_SLOPE,
                                       coverage_ok=len(points) >= MIN_POINTS,
                                       fidelity_ok=fid["gates_met"],
                                       budget_left=session.budget_left())
            if decision != "continue":
                stop_reason = decision
                break
    except BudgetExceeded:
        decision, stop_reason = "inconclusive_budget", "inconclusive_budget"

    counters = {}
    events = []
    try:
        if session.instance_id:
            counters = session.counters()
            events = session.events()
    except Exception:
        pass
    axes = base_axes(counters.get("side_effect_attempts"))
    fid = fidelity.report(axes, ctx.hazard.get("min_fidelity", {}))
    measurements = {
        "points": points, "queue_slope_per_request": ts, "m": m,
        "failure_rate_dialed": FAILURE_RATE, "z_per_round": zs,
        "baseline": baseline, "reference": ref_source,
        "retries": counters.get("retries"), "failures": counters.get("failures"),
        "side_effect_attempts": counters.get("side_effect_attempts"),
    }
    out = {"measurements": measurements, "fidelity_axes": axes,
           "fidelity_report": fid, "stop_reason": stop_reason,
           "action_log": list(session.log)}

    if decision == "fail":
        cx = counterexample.build(
            ctx.request, ctx.hazard, TEMPLATE, session.log,
            expected_stable={"queue_delta_per_round":
                             baseline["queue_delta_per_round"],
                             "m_below": 1.0, "source": ref_source},
            observed_candidate={"queue_slope_per_request": ts, "m": m,
                                "points": points, "final_counters": counters,
                                "events_digest": counterexample.events_digest(events),
                                "divergence_event_seq":
                                    divergence["seq"] if divergence else None},
            first_divergence_age=divergence["age"] if divergence else None,
            seed=ctx.seed, spec_digest=ctx.spec_digest)
        out.update(disposition="counterexample", counterexample=cx)
    elif decision == "pass":
        out["disposition"] = "within_envelope"
    elif decision == "inconclusive_budget":
        out.update(disposition="inconclusive", stop_reason="inconclusive_budget")
    else:
        out["disposition"] = "inconclusive"
    session.destroy()
    return out
