"""Policy v2 temporal-evidence rule: fast-forward outcomes at the T+30
decision stage. Inconclusive or unsupported temporal evidence must never
become a pass — absence of evidence included."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-servers" / "gcp"))

import envelope as minting  # the gcp-observe side (signs)
from rollout_intel.policy import PolicyPack, evaluate

PACK = PolicyPack(str(Path(__file__).parent.parent.parent / "policies" / "rollout-slo.yaml"))


def metric(metric_type: str, value: float, samples: int = 10000) -> dict:
    return minting.mint(
        "metric_window", {"service": "t"},
        {"metric_type": metric_type,
         "series": [{"metric": metric_type, "points": [{"end": "x", "value": value}]}]},
        {"completeness": "COMPLETE", "sample_count": samples},
    )


def logs(entries: list[dict]) -> dict:
    return minting.mint("log_scan", {"service": "t"}, {"query": "q", "entries": entries},
                        {"entry_count": len(entries)})


def ff_result(outcome: str, cx_ids: list[str] | None = None) -> dict:
    """A fastforward_result envelope as rollout-fastforward mints it."""
    return minting.mint(
        "fastforward_result",
        {"service": "t", "episode_id": "ep_test", "stage": "T+30"},
        {"outcome": outcome, "request_id": "ffr_test", "episode_id": "ep_test",
         "service": "t",
         "hazards": [{"hazard_id": "hz_0123456789abcdef", "class": "resource_lifecycle",
                      "disposition": "examined", "mode": "direct"}],
         "fidelity": {"axes": {}, "aggregate": 0.9, "gates_met": True, "unsupported": []},
         "budget": {"granted": {"max_probe_seconds": 60, "max_steps": 6},
                    "spent": {"probe_seconds": 12, "steps": 3}},
         "plan_digest": "pl_0123456789abcdef",
         "counterexample_ids": cx_ids or []},
        source="rollout-fastforward", ttl_seconds=86400)


def healthy_t30() -> list[dict]:
    """Every non-temporal T+30 rule satisfied."""
    return [
        metric("request_count", 24000, samples=24000),
        metric("request_latencies", 188.0),
        metric("http_5xx_rate", 0.003),
        logs([{"ts": "x", "severity": "INFO", "text": "steady state"}]),
    ]


def temporal_rule(out: dict) -> dict:
    return next(r for r in out["rule_results"] if r["rule_id"] == "temporal-evidence")


def test_pack_is_version_2():
    assert PACK.version == "rollout-slo@2"


def test_counterexample_fails_rule_and_overall():
    envs = healthy_t30() + [ff_result("temporal_counterexample", ["cx_ab12cd34ef56"])]
    out = evaluate(PACK, "T+30", envs)
    assert out["policy_status"] == "fail"
    rule = temporal_rule(out)
    assert rule["status"] == "fail"
    assert rule["observed"] == "temporal_counterexample"
    assert "cx_ab12cd34ef56" in rule["note"]
    assert rule["observation_ids"]


def test_inconclusive_budget_is_insufficient_never_pass():
    out = evaluate(PACK, "T+30", healthy_t30() + [ff_result("inconclusive_budget")])
    assert out["policy_status"] == "insufficient_evidence"
    rule = temporal_rule(out)
    assert rule["status"] == "insufficient"
    assert rule["observed"] == "inconclusive_budget"
    assert "inconclusive" in rule["note"]


def test_unsupported_temporal_risk_is_insufficient():
    out = evaluate(PACK, "T+30", healthy_t30() + [ff_result("unsupported_temporal_risk")])
    assert out["policy_status"] == "insufficient_evidence"
    assert temporal_rule(out)["status"] == "insufficient"


def test_benign_outcomes_pass():
    for outcome in ("no_material_temporal_hazard", "bounded_future_envelope",
                    "projected_boundary"):
        out = evaluate(PACK, "T+30", healthy_t30() + [ff_result(outcome)])
        assert out["policy_status"] == "pass", outcome
        rule = temporal_rule(out)
        assert rule["status"] == "pass" and rule["observed"] == outcome


def test_absent_ff_envelope_at_t30_is_insufficient():
    # Every other rule satisfied by a full healthy bundle — the missing
    # temporal evidence alone holds the stage at insufficient_evidence.
    out = evaluate(PACK, "T+30", healthy_t30())
    assert out["policy_status"] == "insufficient_evidence"
    assert out["required_missing"] == ["temporal-evidence"]
    rule = temporal_rule(out)
    assert rule["status"] == "insufficient"
    assert "no temporal fast-forward evidence" in rule["note"]


def test_broken_sig_ff_envelope_satisfies_nothing():
    env = ff_result("no_material_temporal_hazard")
    env["sig"] = "0" * 64  # forged/tampered signature
    out = evaluate(PACK, "T+30", healthy_t30() + [env])
    assert out["policy_status"] == "insufficient_evidence"
    assert temporal_rule(out)["status"] == "insufficient"
    assert any(u.get("reason") == "bad signature"
               for u in out["unverified_observations"])


def test_earlier_stages_unaffected_by_temporal_rule():
    # The rule is scoped to T+30 only: earlier stages neither require nor
    # evaluate temporal evidence.
    t5 = [metric("request_count", 24000, samples=24000),
          metric("request_latencies", 188.0), metric("http_5xx_rate", 0.003)]
    for stage, envs in (
        ("T+0", [minting.mint("workload_state", {}, {"services": [{"name": "t"}]})]),
        ("T+5", t5),
        ("T+15", t5 + [logs([])]),
    ):
        out = evaluate(PACK, stage, envs)
        assert out["policy_status"] == "pass", stage
        assert all(r["rule_id"] != "temporal-evidence" for r in out["rule_results"])
