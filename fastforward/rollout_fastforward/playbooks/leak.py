"""resource_lifecycle_v1: does the candidate leak handles per lifecycle?

Warm-up cycles are EXCLUDED from estimation — a clean pool legitimately
warms to its plateau, and counting that as growth would manufacture a leak.
The reference envelope comes from the stable profile, else a paired clean
run against the previous revision's spec; with neither, the verdict is
inconclusive — never a silent pass.
"""

from .. import counterexample, fidelity, profiles, stopping
from ..probes import BudgetExceeded, ProbeSession
from ..stats import mad, theil_sen, time_to_threshold
from . import base_axes, median

TEMPLATE = "resource_lifecycle_v1"
WARMUP_CYCLES = 100
ROUND_CYCLES = 100
MAX_ROUNDS = 8
MIN_POINTS = 4
PROD_CYCLES_PER_MIN = 60.0  # production lifecycle churn the slope maps onto
Z_DIVERGE = 3.0


def _baseline(ctx):
    """(stats, source): stable profile first, else a paired clean run with
    the same seed and drive, else (None, "none")."""
    if ctx.profiles is not None and ctx.clean_spec_digest:
        fp = profiles.env_fingerprint({"spec_digest": ctx.clean_spec_digest})
        st = ctx.profiles.get(ctx.service, TEMPLATE, fp)
        if st and "slope_per_cycle" in st:
            return st, "profile"
    if ctx.clean_spec is None:
        return None, "none"
    s = ProbeSession(ctx.target, ctx.budget_s, ctx.deadline_at)
    try:
        s.create(ctx.service, ctx.previous_revision or "baseline",
                 ctx.seed, ctx.clean_spec)
        s.cycle(WARMUP_CYCLES)
        prev = s.counters()["open_handles"]
        deltas = []
        for _ in range(MIN_POINTS):
            s.cycle(ROUND_CYCLES)
            cur = s.counters()["open_handles"]
            deltas.append((cur - prev) / ROUND_CYCLES)
            prev = cur
    finally:
        s.destroy()
    return {"slope_per_cycle": {"median": median(deltas), "mad": mad(deltas),
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
    decision, stop_reason = "continue", "max_rounds"
    harm_slope = safe_slope = None
    base_handles = 0
    try:
        session.create(ctx.service, ctx.revision, ctx.seed, ctx.spec)
        session.cycle(WARMUP_CYCLES)  # excluded from estimation
        base_handles = session.counters()["open_handles"]
        threshold = ctx.spec.get("handle_threshold", 1000)
        # Slope that crosses the handle threshold within the policy horizon
        # at production churn — the harm line; a quarter of it is safe.
        harm_slope = (threshold - base_handles) / (ctx.horizon_min * PROD_CYCLES_PER_MIN)
        safe_slope = harm_slope / 4.0
        fid = fidelity.report(base_axes(0), ctx.hazard.get("min_fidelity", {}))
        prev = base_handles
        for rnd in range(MAX_ROUNDS):
            session.cycle(ROUND_CYCLES)
            c = session.counters()
            points.append((c["cycles"], c["open_handles"]))
            delta = (c["open_handles"] - prev) / ROUND_CYCLES
            prev = c["open_handles"]
            zval = profiles.z(delta, baseline, "slope_per_cycle")
            zs.append(zval)
            if divergence is None and zval > Z_DIVERGE:
                ev = session.events()[-1]  # this round's cycle event
                divergence = {"age": ev["age"], "seq": ev["seq"], "round": rnd}
            if len(points) < MIN_POINTS:
                continue
            ts = theil_sen(points)
            decision = stopping.decide(ts["lo"], ts["hi"], harm_slope, safe_slope,
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
        "points": points, "slope_per_cycle": ts, "z_per_round": zs,
        "baseline": baseline, "reference": ref_source,
        "harm_slope": harm_slope, "safe_slope": safe_slope,
        "warmup_cycles_excluded": WARMUP_CYCLES, "base_handles": base_handles,
        "time_to_threshold_min": time_to_threshold(
            counters.get("open_handles", 0), ts["slope"],
            ctx.spec.get("handle_threshold", 1000), PROD_CYCLES_PER_MIN)
        if points else None,
        "side_effect_attempts": counters.get("side_effect_attempts"),
    }
    out = {"measurements": measurements, "fidelity_axes": axes,
           "fidelity_report": fid, "stop_reason": stop_reason,
           "action_log": list(session.log)}

    if decision == "fail":
        cx = counterexample.build(
            ctx.request, ctx.hazard, TEMPLATE, session.log,
            expected_stable={"slope_per_cycle": baseline["slope_per_cycle"],
                             "source": ref_source},
            observed_candidate={"slope_per_cycle": ts, "points": points,
                                "final_counters": counters,
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
