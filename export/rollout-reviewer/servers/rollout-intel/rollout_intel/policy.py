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


# Ladder used when a policy pack has no `checkpoints:` block — the
# pre-dynamic-scheduling defaults, kept so existing packs behave
# identically.
LEGACY_LADDER = [
    {"stage": "T+0", "offset_minutes": 0},
    {"stage": "T+5", "offset_minutes": 5},
    {"stage": "T+15", "offset_minutes": 15},
    {"stage": "T+30", "offset_minutes": 30},
]
LEGACY_BOUNDS = {"min_interval_minutes": 1.0, "max_interval_minutes": 60.0}
LEGACY_HORIZONS = ["30m", "2h", "24h"]


class PolicyPack:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        self.name: str = doc["name"]
        self.version: str = f"{doc['name']}@{doc['version']}"
        self.rules: list[dict] = doc["rules"]

        # Checkpoint schedule: the policy owns the ladder, its bounds, and
        # the exit criteria (dynamic scheduling). Stage names are whatever
        # the ladder declares — nothing else treats them as magic strings.
        cp = doc.get("checkpoints") or {}
        ladder = cp.get("ladder") or LEGACY_LADDER
        self.stages: list[str] = [s["stage"] for s in ladder]
        self.offsets: dict[str, float] = {
            s["stage"]: float(s["offset_minutes"]) for s in ladder}
        self.next_chain: dict[str, float | None] = {}
        for i, s in enumerate(ladder):
            self.next_chain[s["stage"]] = (
                float(ladder[i + 1]["offset_minutes"]) - float(s["offset_minutes"])
                if i + 1 < len(ladder) else None)
        bounds = cp.get("bounds") or {}
        self.bounds: dict[str, float] = {
            "min_interval_minutes": float(bounds.get(
                "min_interval_minutes", LEGACY_BOUNDS["min_interval_minutes"])),
            "max_interval_minutes": float(bounds.get(
                "max_interval_minutes", LEGACY_BOUNDS["max_interval_minutes"])),
        }
        self.exit_criteria: dict = cp.get("exit") or {}
        self.outcome_horizons: list[str] = (
            doc.get("outcome_horizons") or list(LEGACY_HORIZONS))
        self.schedule: dict = {
            "ladder": ladder,
            "bounds": self.bounds,
            "exit": self.exit_criteria,
            "outcome_horizons": self.outcome_horizons,
        }

        # Load-time validation: a malformed pack must fail HERE, not as a
        # KeyError (or a silent mis-schedule) inside a live checkpoint.
        # Threshold keys _evaluate_rule reads with rule[...] — every other
        # rule key it uses has a default.
        required_key = {"min_samples": "min_count", "p99_max": "max_ms",
                        "error_rate_max": "max_rate"}
        for rule in self.rules:
            key = required_key.get(rule.get("type"))
            if key is not None and key not in rule:
                raise ValueError(
                    f"policy {self.version}: rule {rule.get('id')!r} "
                    f"(type {rule['type']}) requires key {key!r}")
        if len(set(self.stages)) != len(self.stages):
            raise ValueError(f"policy {self.version}: ladder stage names "
                             f"must be unique, got {self.stages}")
        raw_offsets = [float(s["offset_minutes"]) for s in ladder]
        if any(b <= a for a, b in zip(raw_offsets, raw_offsets[1:])):
            raise ValueError(f"policy {self.version}: ladder offsets must be "
                             f"strictly increasing, got {raw_offsets}")
        if (self.bounds["min_interval_minutes"]
                > self.bounds["max_interval_minutes"]):
            raise ValueError(
                f"policy {self.version}: min_interval_minutes "
                f"{self.bounds['min_interval_minutes']} exceeds "
                f"max_interval_minutes {self.bounds['max_interval_minutes']}")
        consecutive = self.exit_criteria.get("consecutive_healthy")
        if consecutive is not None and (isinstance(consecutive, bool)
                                        or not isinstance(consecutive, int)
                                        or consecutive < 1):
            raise ValueError(f"policy {self.version}: exit "
                             f"consecutive_healthy must be a positive int, "
                             f"got {consecutive!r}")

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


def evaluate(pack: PolicyPack, stage: str, envelopes: list[dict]) -> dict:
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

    return RuleResult(rid, "insufficient", note=f"unknown rule type {rtype}")
