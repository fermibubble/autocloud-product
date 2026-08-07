"""Experiment planner: hazards -> ordered, budget/deadline-feasible steps.

Signals are preferred (cheap, real telemetry) with a conditional probe
escalation behind them; probe-only hazards (clock_expiry) go straight to
the probe, which is why FF_MODE=signal_only structurally leaves them
unresolved — a signal cannot see an event-sequence bug. Steps a budget or
deadline trims off are recorded unresolved with a budget-shaped
disposition: starvation is inconclusive_budget, never a pass.
"""

import hashlib
import json

from . import inventory

SIGNAL_COST_S = 5.0
PROBE_COST_S = 30.0          # doubles without a ProfileStore (paired clean run)
RUN_IF_SIGNAL_INCONCLUSIVE = "signal_inconclusive"
STOP_ALL_IF = "counterexample_high_impact"


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def plan_digest(steps: list[dict]) -> str:
    basis = [[s["hazard_id"], s["mode"], s["template"]] for s in steps]
    return "pd_" + hashlib.sha256(_canonical(basis)).hexdigest()[:16]


def _step(hazard: dict, mode: str, template: str, cost: float,
          run_if: str | None) -> dict:
    return {"hazard_id": hazard["hazard_id"], "mode": mode, "template": template,
            "cost_est_s": cost, "run_if": run_if, "state": "pending",
            "decision_relevance": hazard.get("decision_relevance") or 0.0}


def _unresolved(hazard: dict, reason: str, disposition: str,
                partial: bool = False) -> dict:
    return {"hazard_id": hazard["hazard_id"], "class": hazard["class"],
            "reason": reason, "disposition": disposition, "partial": partial}


def plan(hazards: list[dict], budget: dict | None, deadline_s: float | None,
         caps: dict, profiles, mode: str = "full") -> dict:
    """{"steps", "unresolved", "plan_digest", "stop_all_if", "mode"}.
    Steps are ordered by decision_relevance desc (hazard_id tie-break),
    deterministic for identical inputs."""
    budget = budget or {}
    probe_cost = PROBE_COST_S * (1 if profiles is not None else 2)
    ordered = sorted(hazards, key=lambda h: (-(h.get("decision_relevance") or 0.0),
                                             h["hazard_id"]))
    steps: list[dict] = []
    unresolved: list[dict] = []
    for h in ordered:
        exps = [e for e in h.get("experiments", [])
                if inventory.executable(e, caps)]
        if mode == "signal_only":
            dropped_probe = any(e.startswith("probe:") for e in exps)
            exps = [e for e in exps if e.startswith("signal:")]
        else:
            dropped_probe = False
        if not exps:
            unresolved.append(_unresolved(
                h, "mode_excluded" if dropped_probe else "no_executable_experiment",
                "unsupported"))
            continue
        signal = next((e for e in exps if e.startswith("signal:")), None)
        probe = next((e for e in exps if e.startswith("probe:")), None)
        if signal:
            steps.append(_step(h, "signal", signal.split(":", 1)[1],
                               SIGNAL_COST_S, None))
            if probe:
                steps.append(_step(h, "probe", probe.split(":", 1)[1],
                                   probe_cost, RUN_IF_SIGNAL_INCONCLUSIVE))
        else:
            steps.append(_step(h, "probe", probe.split(":", 1)[1],
                               probe_cost, None))

    by_hazard = {h["hazard_id"]: h for h in ordered}

    def trim(pred, limit, reason):
        """Drop lowest-relevance matching steps (list tail first) until the
        summed cost of matching steps fits the limit."""
        while sum(s["cost_est_s"] for s in steps if pred(s)) > limit:
            victim = next(s for s in reversed(steps) if pred(s))
            steps.remove(victim)
            h = by_hazard[victim["hazard_id"]]
            partial = any(s["hazard_id"] == victim["hazard_id"] for s in steps)
            unresolved.append(_unresolved(h, reason, "inconclusive_budget", partial))

    max_steps = budget.get("max_steps")
    if isinstance(max_steps, int):
        while len(steps) > max_steps:
            victim = steps[-1]
            steps.remove(victim)
            h = by_hazard[victim["hazard_id"]]
            partial = any(s["hazard_id"] == victim["hazard_id"] for s in steps)
            unresolved.append(_unresolved(h, "budget_max_steps",
                                          "inconclusive_budget", partial))
    max_probe_s = budget.get("max_probe_seconds")
    if isinstance(max_probe_s, (int, float)):
        trim(lambda s: s["mode"] == "probe", max_probe_s, "budget_probe_seconds")
    if isinstance(deadline_s, (int, float)):
        trim(lambda s: True, deadline_s, "deadline")

    # A later trim can remove a hazard's remaining step — settle "partial"
    # (does the hazard still have ANY step?) only after all trimming.
    stepped = {s["hazard_id"] for s in steps}
    for u in unresolved:
        u["partial"] = u["hazard_id"] in stepped

    return {"steps": steps, "unresolved": unresolved,
            "plan_digest": plan_digest(steps), "stop_all_if": STOP_ALL_IF,
            "mode": mode}
