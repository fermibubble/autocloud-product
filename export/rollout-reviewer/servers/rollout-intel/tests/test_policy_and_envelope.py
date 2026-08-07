"""Tests for the deterministic policy layer and the envelope evidence contract.

Envelopes are minted with the REAL signing side (servers/gcp-observe/envelope.py,
loaded by path) and verified by rollout_intel.envelope — the pair of files is the
evidence contract, so tests exercise that pair, not a reimplementation.
"""

import calendar
import importlib.util
import time
from pathlib import Path

import pytest
import yaml

from rollout_intel import envelope as verify_side
from rollout_intel.policy import PolicyPack, evaluate

# --- load the minting side (gcp-observe) by path -----------------------------

_MINT_PATH = Path(__file__).resolve().parents[2] / "gcp-observe" / "envelope.py"
_spec = importlib.util.spec_from_file_location("gcp_observe_envelope", _MINT_PATH)
_mint_side = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mint_side)
mint = _mint_side.mint

STAGE = "S"
SCOPE = {"service": "svc", "region": "r1"}


# --- helpers -----------------------------------------------------------------

def make_pack(tmp_path, rules, extra=None):
    doc = {"name": "test-pack", "version": 1, "rules": rules}
    if extra:
        doc.update(extra)
    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return PolicyPack(str(path))


def single_rule(tmp_path, rule, envs):
    pack = make_pack(tmp_path, [rule])
    verdict = evaluate(pack, STAGE, envs)
    assert len(verdict["rule_results"]) == 1
    return verdict["rule_results"][0], verdict


def mint_metric(metric_type, values, quality=None):
    payload = {
        "metric_type": metric_type,
        "series": [{"points": [{"value": v} for v in values]}],
    }
    return mint("metric_window", SCOPE, payload, quality=quality)


def mint_workload(services):
    return mint("workload_state", SCOPE, {"services": services})


def mint_logs(entries):
    return mint("log_scan", SCOPE, {"entries": entries})


def wl_rule():
    return {"id": "wl", "type": "workload_serving", "stages": [STAGE]}


def samples_rule(min_count=100):
    return {"id": "samples", "type": "min_samples",
            "metric_contains": "request_count", "min_count": min_count,
            "stages": [STAGE]}


def p99_rule(max_ms=250):
    return {"id": "p99", "type": "p99_max", "metric_contains": "latenc",
            "max_ms": max_ms, "stages": [STAGE]}


def err_rule(max_rate=0.005):
    return {"id": "err", "type": "error_rate_max", "metric_contains": "5xx",
            "max_rate": max_rate, "stages": [STAGE]}


def fatal_rule():
    return {"id": "fatal", "type": "no_new_fatal", "pattern": "FATAL",
            "stages": [STAGE]}


# --- envelope.verify ---------------------------------------------------------

def test_minted_envelope_verifies():
    ok, reason = verify_side.verify(mint_workload([{"name": "svc"}]))
    assert ok
    assert reason == "ok"


def test_forged_sig_value_is_bad_signature():
    env = mint_workload([{"name": "svc"}])
    env["sig"] = "0" * 64
    ok, reason = verify_side.verify(env)
    assert not ok
    assert reason == "bad signature"


def test_tampering_a_signed_field_is_bad_signature():
    env = mint_workload([{"name": "svc"}])
    env["observed_at"] = "1999-01-01T00:00:00Z"
    ok, reason = verify_side.verify(env)
    assert not ok
    assert reason == "bad signature"


def test_tampering_payload_after_mint_is_payload_hash_mismatch():
    env = mint_workload([{"name": "svc"}])
    env["payload"]["services"].append({"name": "injected"})
    ok, reason = verify_side.verify(env)
    assert not ok
    assert reason == "payload hash mismatch"


def test_verify_past_fresh_until_is_stale():
    env = mint_workload([{"name": "svc"}])
    ok, reason = verify_side.verify(env, now=time.time() + 3600)
    assert not ok
    assert reason.startswith("stale (fresh_until ")


def test_fresh_until_deadline_is_inclusive():
    env = mint_workload([{"name": "svc"}])
    deadline = float(calendar.timegm(
        time.strptime(env["fresh_until"], "%Y-%m-%dT%H:%M:%SZ")))
    ok, _ = verify_side.verify(env, now=deadline)
    assert ok
    ok, reason = verify_side.verify(env, now=deadline + 1)
    assert not ok
    assert reason.startswith("stale")


def test_malformed_inputs_report_malformed_not_crash():
    ok, reason = verify_side.verify([])  # not a dict at all
    assert not ok
    assert reason.startswith("malformed:")

    env = mint_workload([{"name": "svc"}])
    env["scope"] = {"not", "json", "serializable"}  # set breaks canonicalization
    ok, reason = verify_side.verify(env)
    assert not ok
    assert reason.startswith("malformed:")


# --- workload_serving --------------------------------------------------------

def test_workload_serving_passes_when_a_service_is_serving(tmp_path):
    env = mint_workload([{"name": "svc", "revision": "r2"}])
    result, _ = single_rule(tmp_path, wl_rule(), [env])
    assert result["status"] == "pass"
    assert result["observed"] == 1
    assert result["observation_ids"] == [env["observation_id"]]


def test_workload_serving_fails_when_no_services_serving(tmp_path):
    result, _ = single_rule(tmp_path, wl_rule(), [mint_workload([])])
    assert result["status"] == "fail"
    assert result["observed"] == 0


def test_workload_serving_without_evidence_is_insufficient(tmp_path):
    result, _ = single_rule(tmp_path, wl_rule(), [])
    assert result["status"] == "insufficient"
    assert result["note"] == "no workload_state observation"


# --- min_samples -------------------------------------------------------------

def test_min_samples_passes_on_quality_sample_count(tmp_path):
    env = mint_metric("run.googleapis.com/request_count", [1.0],
                      quality={"sample_count": 150})
    result, _ = single_rule(tmp_path, samples_rule(min_count=100), [env])
    assert result["status"] == "pass"
    assert result["observed"] == 150
    assert result["threshold"] == 100


def test_min_samples_below_threshold_is_insufficient_not_fail(tmp_path):
    env = mint_metric("request_count", [1.0], quality={"sample_count": 10})
    result, verdict = single_rule(tmp_path, samples_rule(min_count=100), [env])
    assert result["status"] == "insufficient"
    assert result["note"] == "below minimum sample count"
    assert verdict["policy_status"] == "insufficient_evidence"


def test_min_samples_falls_back_to_latest_series_value(tmp_path):
    env = mint_metric("request_count", [40.0, 500.0])  # default quality: no sample_count
    result, _ = single_rule(tmp_path, samples_rule(min_count=100), [env])
    assert result["status"] == "pass"
    assert result["observed"] == 500.0


def test_min_samples_without_count_metric_is_insufficient(tmp_path):
    other = mint_metric("latency", [10.0])  # wrong metric_type: not found
    result, _ = single_rule(tmp_path, samples_rule(), [other])
    assert result["status"] == "insufficient"
    assert result["note"] == "no request-count observation"


# --- p99_max -----------------------------------------------------------------

def test_p99_at_threshold_passes(tmp_path):
    env = mint_metric("request_latencies", [180.0, 250.0])
    result, _ = single_rule(tmp_path, p99_rule(max_ms=250), [env])
    assert result["status"] == "pass"
    assert result["observed"] == 250.0  # newest point wins; boundary inclusive


def test_p99_above_threshold_fails(tmp_path):
    env = mint_metric("request_latencies", [200.0, 300.0])
    result, _ = single_rule(tmp_path, p99_rule(max_ms=250), [env])
    assert result["status"] == "fail"
    assert result["observed"] == 300.0


def test_p99_without_latency_metric_is_insufficient(tmp_path):
    result, _ = single_rule(tmp_path, p99_rule(), [])
    assert result["status"] == "insufficient"
    assert result["note"] == "no latency observation"


def test_p99_empty_series_is_insufficient(tmp_path):
    env = mint_metric("request_latencies", [])
    result, _ = single_rule(tmp_path, p99_rule(), [env])
    assert result["status"] == "insufficient"
    assert result["note"] == "empty series"
    assert result["observation_ids"] == [env["observation_id"]]


# --- error_rate_max ----------------------------------------------------------

def test_error_rate_within_threshold_passes(tmp_path):
    env = mint_metric("5xx_rate", [0.001])
    result, _ = single_rule(tmp_path, err_rule(max_rate=0.005), [env])
    assert result["status"] == "pass"
    assert result["observed"] == 0.001


def test_error_rate_above_threshold_fails(tmp_path):
    env = mint_metric("5xx_rate", [0.02])
    result, _ = single_rule(tmp_path, err_rule(max_rate=0.005), [env])
    assert result["status"] == "fail"


def test_error_rate_without_metric_is_insufficient(tmp_path):
    result, _ = single_rule(tmp_path, err_rule(), [])
    assert result["status"] == "insufficient"
    assert result["note"] == "no error-rate observation"


def test_error_rate_empty_series_is_insufficient(tmp_path):
    env = mint_metric("5xx_rate", [])
    result, _ = single_rule(tmp_path, err_rule(), [env])
    assert result["status"] == "insufficient"
    assert result["note"] == "empty series"


# --- no_new_fatal ------------------------------------------------------------

def test_no_new_fatal_passes_when_no_entry_matches(tmp_path):
    env = mint_logs([
        {"severity": "INFO", "text": "FATAL mentioned at INFO is not counted"},
        {"severity": "ERROR", "text": "plain error, no pattern hit"},
    ])
    result, _ = single_rule(tmp_path, fatal_rule(), [env])
    assert result["status"] == "pass"
    assert result["observed"] == "0 matching entries"
    assert result["note"] == ""


def test_no_new_fatal_fails_on_matching_error_entry(tmp_path):
    env = mint_logs([
        {"severity": "ERROR", "text": "FATAL: connection pool exhausted"},
        {"severity": "CRITICAL", "text": "FATAL: OOM"},
    ])
    result, _ = single_rule(tmp_path, fatal_rule(), [env])
    assert result["status"] == "fail"
    assert result["observed"] == "2 matching entries"
    assert result["note"] == "FATAL: connection pool exhausted"


def test_no_new_fatal_without_log_scan_is_insufficient(tmp_path):
    result, _ = single_rule(tmp_path, fatal_rule(), [])
    assert result["status"] == "insufficient"
    assert result["note"] == "no log_scan observation"


def test_unknown_rule_type_is_insufficient(tmp_path):
    rule = {"id": "mystery", "type": "quantum_vibes", "stages": [STAGE]}
    result, _ = single_rule(tmp_path, rule, [])
    assert result["status"] == "insufficient"
    assert result["note"] == "unknown rule type quantum_vibes"


# --- evaluate(): overall status ----------------------------------------------

def test_any_rule_fail_makes_overall_fail(tmp_path):
    pack = make_pack(tmp_path, [wl_rule(), p99_rule(max_ms=250)])
    envs = [mint_workload([{"name": "svc"}]),
            mint_metric("request_latencies", [900.0])]
    verdict = evaluate(pack, STAGE, envs)
    assert verdict["policy_status"] == "fail"
    assert verdict["required_missing"] == []


def test_insufficient_rule_makes_overall_insufficient_evidence(tmp_path):
    pack = make_pack(tmp_path, [wl_rule(), p99_rule()])
    verdict = evaluate(pack, STAGE, [mint_workload([{"name": "svc"}])])
    assert verdict["policy_status"] == "insufficient_evidence"
    assert verdict["required_missing"] == ["p99"]


def test_fail_outranks_insufficient(tmp_path):
    pack = make_pack(tmp_path, [wl_rule(), p99_rule()])
    verdict = evaluate(pack, STAGE, [mint_workload([])])  # wl fails, p99 missing
    assert verdict["policy_status"] == "fail"
    assert verdict["required_missing"] == ["p99"]


def test_stage_with_no_rules_is_insufficient_evidence(tmp_path):
    pack = make_pack(tmp_path, [wl_rule()])  # rule only applies at STAGE
    verdict = evaluate(pack, "T+999", [mint_workload([{"name": "svc"}])])
    assert verdict["rule_results"] == []
    assert verdict["policy_status"] == "insufficient_evidence"


def test_all_rules_pass_is_overall_pass(tmp_path):
    pack = make_pack(tmp_path, [wl_rule(), p99_rule(), err_rule()])
    envs = [mint_workload([{"name": "svc"}]),
            mint_metric("request_latencies", [120.0]),
            mint_metric("5xx_rate", [0.0])]
    verdict = evaluate(pack, STAGE, envs)
    assert verdict["policy_status"] == "pass"
    assert verdict["policy_version"] == "test-pack@1"
    assert verdict["stage"] == STAGE
    assert verdict["unverified_observations"] == []


def test_tampered_envelope_satisfies_nothing(tmp_path):
    env = mint_workload([{"name": "svc"}])
    env["payload"]["services"][0]["name"] = "edited-after-mint"
    result, verdict = single_rule(tmp_path, wl_rule(), [env])
    assert result["status"] == "insufficient"
    assert verdict["policy_status"] == "insufficient_evidence"
    assert verdict["unverified_observations"] == [
        {"observation_id": env["observation_id"], "reason": "payload hash mismatch"}
    ]


def test_stale_envelope_satisfies_nothing(tmp_path):
    env = mint("workload_state", SCOPE, {"services": [{"name": "svc"}]},
               ttl_seconds=-3600)
    result, verdict = single_rule(tmp_path, wl_rule(), [env])
    assert result["status"] == "insufficient"
    assert len(verdict["unverified_observations"]) == 1
    assert verdict["unverified_observations"][0]["reason"].startswith("stale")


# --- PolicyPack schedule parsing ---------------------------------------------

def test_custom_checkpoints_block_defines_the_schedule(tmp_path):
    pack = make_pack(tmp_path, [], extra={
        "checkpoints": {
            "ladder": [
                {"stage": "A", "offset_minutes": 0},
                {"stage": "B", "offset_minutes": 7},
                {"stage": "C", "offset_minutes": 20},
            ],
            "bounds": {"min_interval_minutes": 3, "max_interval_minutes": 45},
            "exit": {"consecutive_healthy": 2, "min_soak_minutes": 20},
        },
        "outcome_horizons": ["1h", "24h"],
    })
    assert pack.stages == ["A", "B", "C"]
    assert pack.offsets == {"A": 0.0, "B": 7.0, "C": 20.0}
    assert pack.next_chain == {"A": 7.0, "B": 13.0, "C": None}
    assert pack.bounds == {"min_interval_minutes": 3.0, "max_interval_minutes": 45.0}
    assert pack.exit_criteria == {"consecutive_healthy": 2, "min_soak_minutes": 20}
    assert pack.outcome_horizons == ["1h", "24h"]
    assert pack.schedule["ladder"][1] == {"stage": "B", "offset_minutes": 7}
    assert pack.schedule["bounds"] is pack.bounds
    assert pack.version == "test-pack@1"


def test_missing_checkpoints_block_falls_back_to_legacy_ladder(tmp_path):
    pack = make_pack(tmp_path, [])
    assert pack.stages == ["T+0", "T+5", "T+15", "T+30"]
    assert pack.offsets == {"T+0": 0.0, "T+5": 5.0, "T+15": 15.0, "T+30": 30.0}
    assert pack.next_chain == {"T+0": 5.0, "T+5": 10.0, "T+15": 15.0, "T+30": None}
    assert pack.bounds == {"min_interval_minutes": 1.0, "max_interval_minutes": 60.0}
    assert pack.exit_criteria == {}
    assert pack.outcome_horizons == ["30m", "2h", "24h"]


def test_partial_bounds_get_legacy_defaults(tmp_path):
    pack = make_pack(tmp_path, [], extra={
        "checkpoints": {
            "ladder": [{"stage": "only", "offset_minutes": 0}],
            "bounds": {"min_interval_minutes": 2},
        },
    })
    assert pack.bounds == {"min_interval_minutes": 2.0, "max_interval_minutes": 60.0}
    assert pack.next_chain == {"only": None}


def test_rule_missing_its_threshold_key_raises_at_load(tmp_path):
    # One per threshold-carrying type: the KeyError must move from
    # mid-episode evaluation to pack load.
    for rule, key in [
        ({"id": "s", "type": "min_samples", "stages": [STAGE]}, "min_count"),
        ({"id": "p", "type": "p99_max", "stages": [STAGE]}, "max_ms"),
        ({"id": "e", "type": "error_rate_max", "stages": [STAGE]}, "max_rate"),
    ]:
        with pytest.raises(ValueError, match=key):
            make_pack(tmp_path, [rule])


def test_non_increasing_ladder_raises_at_load(tmp_path):
    with pytest.raises(ValueError, match="strictly increasing"):
        make_pack(tmp_path, [], extra={"checkpoints": {"ladder": [
            {"stage": "A", "offset_minutes": 0},
            {"stage": "B", "offset_minutes": 10},
            {"stage": "C", "offset_minutes": 10},
        ]}})


def test_duplicate_ladder_stage_names_raise_at_load(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        make_pack(tmp_path, [], extra={"checkpoints": {"ladder": [
            {"stage": "A", "offset_minutes": 0},
            {"stage": "A", "offset_minutes": 10},
        ]}})


def test_inverted_interval_bounds_raise_at_load(tmp_path):
    with pytest.raises(ValueError, match="min_interval_minutes"):
        make_pack(tmp_path, [], extra={"checkpoints": {
            "ladder": [{"stage": "A", "offset_minutes": 0}],
            "bounds": {"min_interval_minutes": 30, "max_interval_minutes": 5},
        }})


def test_non_positive_consecutive_healthy_raises_at_load(tmp_path):
    with pytest.raises(ValueError, match="consecutive_healthy"):
        make_pack(tmp_path, [], extra={"checkpoints": {
            "ladder": [{"stage": "A", "offset_minutes": 0}],
            "exit": {"consecutive_healthy": 0, "min_soak_minutes": 5},
        }})


def test_rules_for_stage_filters_by_declared_stages(tmp_path):
    rules = [
        {"id": "a", "type": "workload_serving", "stages": ["T+0"]},
        {"id": "b", "type": "p99_max", "max_ms": 1, "stages": ["T+0", "T+5"]},
        {"id": "c", "type": "error_rate_max", "max_rate": 1},  # no stages key
    ]
    pack = make_pack(tmp_path, rules)
    assert [r["id"] for r in pack.rules_for_stage("T+0")] == ["a", "b"]
    assert [r["id"] for r in pack.rules_for_stage("T+5")] == ["b"]
    assert pack.rules_for_stage("T+30") == []


def test_shipped_pack_parses_with_its_declared_schedule():
    shipped = Path(__file__).resolve().parents[1] / "policies" / "rollout-slo.yaml"
    pack = PolicyPack(str(shipped))
    assert pack.version == "rollout-slo@1"
    assert pack.stages == ["T+0", "T+5", "T+15", "T+30"]
    assert pack.bounds == {"min_interval_minutes": 2.0, "max_interval_minutes": 60.0}
    assert pack.next_chain["T+15"] == 15.0
    assert pack.exit_criteria == {"consecutive_healthy": 2, "min_soak_minutes": 30}
