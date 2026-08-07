"""Deterministic policy evaluation — the layer the LLM cannot override.

Rules live in a versioned YAML pack (policies/rollout-slo.yaml). Evaluation
consumes ONLY verified observation envelopes:

  1. Verify every envelope (signature, hash, freshness) — failures go to
     unverified_observations and satisfy nothing.
  2. For each rule applicable to the stage, locate its required evidence
     among verified envelopes; missing evidence => that rule reports
     insufficient, never pass.
  3. Overall: any rule fail => fail; else any insufficient =>
     insufficient_evidence; else pass.

INSUFFICIENT_EVIDENCE is a first-class outcome, not an error path.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from . import envelope


@dataclass
class RuleResult:
    rule_id: str
    status: str  # pass | fail | insufficient
    observed: Any = None
    threshold: Any = None
    observation_ids: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id, "status": self.status,
            "observed": self.observed, "threshold": self.threshold,
            "observation_ids": self.observation_ids, "note": self.note,
        }


class PolicyPack:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        self.name: str = doc["name"]
        self.version: str = f"{doc['name']}@{doc['version']}"
        self.rules: list[dict] = doc["rules"]
        self.defaults: dict = doc.get("defaults", {})

    def rules_for_stage(self, stage: str) -> list[dict]:
        return [r for r in self.rules if stage in r.get("stages", [])]

    def summary(self) -> list[str]:
        return [f"{r['id']}: {r.get('description', r['type'])}" for r in self.rules]


def _latest_value(env: dict) -> float | None:
    """Newest point value from a metric_window envelope."""
    for series in env.get("payload", {}).get("series", []):
        points = series.get("points", [])
        if points:
            value = points[-1].get("value")
            if value is not None:
                return float(value)
    return None


def _find_metric(envs: list[dict], contains: str) -> dict | None:
    for env in envs:
        if env.get("type") != "metric_window":
            continue
        if contains in (env.get("payload", {}).get("metric_type") or ""):
            return env
    return None


def _find_type(envs: list[dict], obs_type: str) -> dict | None:
    for env in envs:
        if env.get("type") == obs_type:
            return env
    return None


def evaluate(pack: PolicyPack, stage: str, envelopes: list[dict],
             service: str = "") -> dict:
    verified: list[dict] = []
    unverified: list[dict] = []
    for env in envelopes:
        ok, reason = envelope.verify(env)
        (verified if ok else unverified).append(
            env if ok else {"observation_id": env.get("observation_id"), "reason": reason}
        )

    results: list[RuleResult] = []
    for rule in pack.rules_for_stage(stage):
        results.append(_evaluate_rule(rule, verified))

    required_missing = [r.rule_id for r in results if r.status == "insufficient"]
    if any(r.status == "fail" for r in results):
        status = "fail"
    elif required_missing or not results:
        status = "insufficient_evidence"
    else:
        status = "pass"
    return {
        "policy_status": status,
        "policy_version": pack.version,
        "stage": stage,
        "rule_results": [r.to_dict() for r in results],
        "required_missing": required_missing,
        "unverified_observations": unverified,
    }


def _evaluate_rule(rule: dict, envs: list[dict]) -> RuleResult:
    rid, rtype = rule["id"], rule["type"]

    if rtype == "workload_serving":
        env = _find_type(envs, "workload_state")
        if env is None:
            return RuleResult(rid, "insufficient", note="no workload_state observation")
        services = env.get("payload", {}).get("services", [])
        return RuleResult(
            rid, "pass" if services else "fail",
            observed=len(services), threshold=">=1 service serving",
            observation_ids=[env["observation_id"]],
        )

    if rtype == "min_samples":
        env = _find_metric(envs, rule.get("metric_contains", "count"))
        threshold = rule["min_count"]
        if env is None:
            return RuleResult(rid, "insufficient", threshold=threshold,
                              note="no request-count observation")
        samples = env.get("quality", {}).get("sample_count") or _latest_value(env) or 0
        status = "pass" if samples >= threshold else "insufficient"
        return RuleResult(rid, status, observed=samples, threshold=threshold,
                          observation_ids=[env["observation_id"]],
                          note="" if status == "pass" else "below minimum sample count")

    if rtype == "p99_max":
        env = _find_metric(envs, rule.get("metric_contains", "latenc"))
        threshold = rule["max_ms"]
        if env is None:
            return RuleResult(rid, "insufficient", threshold=threshold,
                              note="no latency observation")
        value = _latest_value(env)
        if value is None:
            return RuleResult(rid, "insufficient", threshold=threshold,
                              observation_ids=[env["observation_id"]], note="empty series")
        return RuleResult(rid, "pass" if value <= threshold else "fail",
                          observed=value, threshold=threshold,
                          observation_ids=[env["observation_id"]])

    if rtype == "error_rate_max":
        env = _find_metric(envs, rule.get("metric_contains", "5xx"))
        threshold = rule["max_rate"]
        if env is None:
            return RuleResult(rid, "insufficient", threshold=threshold,
                              note="no error-rate observation")
        value = _latest_value(env)
        if value is None:
            return RuleResult(rid, "insufficient", threshold=threshold,
                              observation_ids=[env["observation_id"]], note="empty series")
        return RuleResult(rid, "pass" if value <= threshold else "fail",
                          observed=value, threshold=threshold,
                          observation_ids=[env["observation_id"]])

    if rtype == "no_new_fatal":
        env = _find_type(envs, "log_scan")
        if env is None:
            return RuleResult(rid, "insufficient", note="no log_scan observation")
        pattern = re.compile(rule.get("pattern", r"FATAL"))
        hits = [
            e for e in env.get("payload", {}).get("entries", [])
            if e.get("severity") in ("ERROR", "CRITICAL") and pattern.search(e.get("text", ""))
        ]
        return RuleResult(rid, "fail" if hits else "pass",
                          observed=f"{len(hits)} matching entries",
                          threshold="0 new fatal patterns",
                          observation_ids=[env["observation_id"]],
                          note=(hits[0]["text"][:120] if hits else ""))

    if rtype == "fastforward_result":
        env = _find_type(envs, "fastforward_result")
        if env is None:
            return RuleResult(rid, "insufficient",
                              note="no temporal fast-forward evidence at decision stage")
        outcome = env.get("payload", {}).get("outcome")
        fail_outcomes = rule.get("fail_outcomes", ["temporal_counterexample"])
        insufficient_outcomes = rule.get(
            "insufficient_outcomes", ["inconclusive_budget", "unsupported_temporal_risk"])
        if outcome in fail_outcomes:
            cx_ids = env.get("payload", {}).get("counterexample_ids", [])
            return RuleResult(rid, "fail", observed=outcome,
                              threshold="no confirmed temporal counterexample",
                              observation_ids=[env["observation_id"]],
                              note=f"confirmed counterexamples: {cx_ids}")
        if outcome in insufficient_outcomes:
            return RuleResult(rid, "insufficient", observed=outcome,
                              observation_ids=[env["observation_id"]],
                              note=f"temporal evidence inconclusive: {outcome}")
        return RuleResult(rid, "pass", observed=outcome,
                          threshold="no confirmed temporal counterexample",
                          observation_ids=[env["observation_id"]])

    return RuleResult(rid, "insufficient", note=f"unknown rule type {rtype}")
