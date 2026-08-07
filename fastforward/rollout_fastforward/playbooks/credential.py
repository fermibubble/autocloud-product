"""cred_lifecycle_v1: the small event-sequence probe for expiry bugs.

No statistics — a deterministic oracle over one transition sequence:
warm connections, verify auth, age the credential past its TTL, rotate the
key, arm one transient refresh fault, then send traffic. A correct client
re-authenticates (one bounded transient failure, then recovery); the seeded
bug reuses the stale credential — stale_reuse_count > 0 IS the divergence,
first observed at that exact event.
"""

from .. import counterexample, fidelity
from ..probes import BudgetExceeded, ProbeSession
from . import base_axes

TEMPLATE = "cred_lifecycle_v1"
WARM_CYCLES = 50
BATCH = 20
CONCURRENCY = 4
ADVANCE_SLACK_S = 60
EXPIRY_AXIS_COVERAGE = 0.9  # this playbook advances its axis explicitly


def _result(disposition, stop_reason, measurements, hazard, side_effects,
            **extra) -> dict:
    axes = base_axes(side_effects)
    out = {"disposition": disposition, "stop_reason": stop_reason,
           "measurements": measurements, "fidelity_axes": axes,
           "fidelity_report": fidelity.report(axes, hazard.get("min_fidelity", {}))}
    out.update(extra)
    return out


def run(ctx) -> dict:
    session = ProbeSession(ctx.target, ctx.budget_s, ctx.deadline_at)
    try:
        session.create(ctx.service, ctx.revision, ctx.seed, ctx.spec)
        session.cycle(WARM_CYCLES)
        session.requests(BATCH, CONCURRENCY)  # baseline: auth must work
        c = session.counters()
        if c["failures"] or c["stale_reuse_count"]:
            out = _result("inconclusive", "baseline_auth_failure",
                          {"counters": c}, ctx.hazard,
                          c.get("side_effect_attempts"))
            session.destroy()
            return out
        ttl = ctx.spec.get("cred_ttl_s", 3600)
        session.advance("cred_age_s", ttl + ADVANCE_SLACK_S)
        session.rotate_key()
        session.refresh_fault(True)
        session.requests(BATCH, CONCURRENCY)  # transient-fault window
        session.requests(BATCH, CONCURRENCY)  # recovery window
    except BudgetExceeded:
        out = _result("inconclusive", "inconclusive_budget", {}, ctx.hazard, None)
        session.destroy()
        return out

    c = session.counters()
    events = session.events()
    stale = next((e for e in events if e["kind"] == "stale_credential_reuse"), None)
    measurements = {
        "counters": c, "ttl_s": ctx.spec.get("cred_ttl_s", 3600),
        "advanced_s": ctx.spec.get("cred_ttl_s", 3600) + ADVANCE_SLACK_S,
        "refresh_failures": c["refresh_failures"],
        "stale_reuse_count": c["stale_reuse_count"],
        "expiry_axis_coverage": EXPIRY_AXIS_COVERAGE,  # clock_coverage in the
        # axes stays the honest inventory value; only THIS axis was advanced.
        "side_effect_attempts": c.get("side_effect_attempts"),
    }

    if stale is not None:
        cx = counterexample.build(
            ctx.request, ctx.hazard, TEMPLATE, session.log,
            expected_stable={"stale_reuse_count": 0, "refresh_failures_max": 1,
                             "recovery": "re-authenticate after rotation+expiry"},
            observed_candidate={"final_counters": c,
                                "events_digest": counterexample.events_digest(events),
                                "stale_event_seq": stale["seq"]},
            first_divergence_age=stale["age"],
            seed=ctx.seed, spec_digest=ctx.spec_digest)
        out = _result("counterexample", "fail", measurements, ctx.hazard,
                      c.get("side_effect_attempts"), counterexample=cx,
                      action_log=list(session.log))
        session.destroy()
        return out

    recovered = (c["stale_reuse_count"] == 0 and c["failures"] == 0
                 and c["refresh_failures"] <= 1 and c["cred_age_s"] == 0)
    out = _result("within_envelope" if recovered else "inconclusive",
                  "pass" if recovered else "no_clean_recovery",
                  measurements, ctx.hazard, c.get("side_effect_attempts"),
                  action_log=list(session.log))
    session.destroy()
    return out
