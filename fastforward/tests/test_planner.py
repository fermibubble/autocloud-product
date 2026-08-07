"""Planner tests: signal preferred with conditional probe escalation,
budget/deadline starvation is recorded (never silently dropped), and the
plan is deterministic."""

from rollout_fastforward import compiler, inventory, planner

CAPS = inventory.capabilities()

LEAK = {"items": [{"kind": "dependency", "name": "pg-pool", "from": "2.1.0", "to": "3.0.0"}]}
RETRY = {"items": [{"kind": "config", "name": "retry_max", "from": 1, "to": 4}]}
CRED = {"items": [{"kind": "dependency", "name": "auth-client", "from": "5.2", "to": "6.0"}]}
SCHEMA = {"items": [{"kind": "schema", "name": "orders", "from": "v3", "to": "v4"}]}
ALL = {"items": LEAK["items"] + RETRY["items"] + CRED["items"]}

BUDGET = {"max_probe_seconds": 300, "max_steps": 8}


def hz(manifest):
    return compiler.compile(manifest, CAPS)


def test_signal_preferred_with_probe_escalation():
    p = planner.plan(hz(LEAK), BUDGET, 240, CAPS, None, "full")
    assert [(s["mode"], s["template"], s["run_if"]) for s in p["steps"]] == [
        ("signal", "growth_projection", None),
        ("probe", "resource_lifecycle_v1", "signal_inconclusive"),
    ]
    assert p["unresolved"] == []


def test_probe_only_hazard_runs_probe_unconditionally():
    p = planner.plan(hz(CRED), BUDGET, 240, CAPS, None, "full")
    assert [(s["mode"], s["template"], s["run_if"]) for s in p["steps"]] == [
        ("probe", "cred_lifecycle_v1", None),
    ]


def test_ordering_by_relevance_desc():
    p = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "full")
    rels = [s["decision_relevance"] for s in p["steps"]]
    assert rels == sorted(rels, reverse=True)
    # 0.9-relevance hazards (leak, cred) precede the 0.85 (retry).
    assert rels[-2:] == [0.85, 0.85]


def test_non_executable_hazard_is_unresolved_unsupported():
    p = planner.plan(hz(SCHEMA), BUDGET, 240, CAPS, None, "full")
    assert p["steps"] == []
    assert len(p["unresolved"]) == 1
    u = p["unresolved"][0]
    assert u["class"] == "state_boundary"
    assert u["disposition"] == "unsupported"
    assert u["reason"] == "no_executable_experiment"


def test_budget_max_steps_records_inconclusive_budget():
    p = planner.plan(hz(ALL), {"max_probe_seconds": 300, "max_steps": 2},
                     600, CAPS, None, "full")
    assert len(p["steps"]) == 2
    dropped = [u for u in p["unresolved"] if u["reason"] == "budget_max_steps"]
    assert dropped and all(u["disposition"] == "inconclusive_budget" for u in dropped)
    # Fully dropped hazards are non-partial; a hazard keeping its signal is partial.
    stepped = {s["hazard_id"] for s in p["steps"]}
    for u in dropped:
        assert u["partial"] == (u["hazard_id"] in stepped)


def test_zero_probe_seconds_drops_every_probe_step():
    p = planner.plan(hz(ALL), {"max_probe_seconds": 0, "max_steps": 8},
                     600, CAPS, None, "full")
    assert all(s["mode"] == "signal" for s in p["steps"])
    reasons = {u["reason"] for u in p["unresolved"]}
    assert reasons == {"budget_probe_seconds"}
    assert all(u["disposition"] == "inconclusive_budget" for u in p["unresolved"])
    # clock_expiry lost its ONLY experiment: non-partial starvation.
    cred = next(u for u in p["unresolved"] if u["class"] == "clock_expiry")
    assert cred["partial"] is False


def test_deadline_trims_lowest_relevance_first():
    full = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "full")
    total = sum(s["cost_est_s"] for s in full["steps"])
    p = planner.plan(hz(ALL), BUDGET, total - 1, CAPS, None, "full")
    assert sum(s["cost_est_s"] for s in p["steps"]) <= total - 1
    dropped = [u for u in p["unresolved"] if u["reason"] == "deadline"]
    assert dropped and all(u["disposition"] == "inconclusive_budget" for u in dropped)
    # The victim is the tail (lowest-relevance) step of the full plan.
    assert dropped[0]["hazard_id"] == full["steps"][-1]["hazard_id"]


def test_signal_only_leaves_clock_expiry_unresolved():
    p = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "signal_only")
    assert all(s["mode"] == "signal" for s in p["steps"])
    cred = next(u for u in p["unresolved"] if u["class"] == "clock_expiry")
    assert cred["reason"] == "mode_excluded"
    assert cred["disposition"] == "unsupported"


def test_stop_all_if_and_digest():
    p = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "full")
    assert p["stop_all_if"] == "counterexample_high_impact"
    assert p["plan_digest"].startswith("pd_") and len(p["plan_digest"]) == 19


def test_deterministic():
    a = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "full")
    b = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "full")
    assert a == b
    c = planner.plan(hz(ALL), BUDGET, 600, CAPS, None, "signal_only")
    assert c["plan_digest"] != a["plan_digest"]


def test_empty_hazards_empty_plan():
    p = planner.plan([], BUDGET, 240, CAPS, None, "full")
    assert p["steps"] == [] and p["unresolved"] == []
    assert p["plan_digest"] == planner.plan([], BUDGET, 240, CAPS, None, "full")["plan_digest"]


def test_probe_cost_doubles_without_profile_store():
    with_p = planner.plan(hz(LEAK), BUDGET, 600, CAPS, object(), "full")
    without = planner.plan(hz(LEAK), BUDGET, 600, CAPS, None, "full")
    cost = {s["mode"]: s["cost_est_s"] for s in with_p["steps"]}
    cost_no = {s["mode"]: s["cost_est_s"] for s in without["steps"]}
    assert cost_no["probe"] == 2 * cost["probe"]
