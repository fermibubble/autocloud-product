"""Hazard compiler: deterministic manifest-traits -> hazard floor.

The floor is non-negotiable: merge_proposals lets an LLM ADD hazards or
RAISE relevance, never remove or downgrade what the manifest compiled —
the deterministic layer cannot be argued out of a hazard. clock_expiry
deliberately has no signal experiment: expiry bugs are event-sequence-only,
which is exactly what a signal-only evaluation arm must miss.
"""

import hashlib

from . import inventory as _inventory
from . import manifest as _manifest

HAZARD_CLASSES = ("resource_lifecycle", "rate_balance", "clock_expiry",
                  "state_boundary", "concurrency", "agent_longevity")


def _trait_match(triggers: frozenset):
    def matched(features: list[str]) -> list[str]:
        return sorted(triggers & set(features))
    return matched


def _flag_match(substrings: tuple):
    def matched(features: list[str]) -> list[str]:
        return sorted(f for f in features
                      if f.startswith("flag:") and any(s in f.lower() for s in substrings))
    return matched


def _sig(klass, matched, age_dimensions, expected_symptom, experiments,
         min_fidelity, impact, decision_relevance) -> dict:
    return {
        "class": klass,
        "matched": matched,
        "fires": lambda features, _m=matched: bool(_m(features)),
        "age_dimensions": age_dimensions,
        "expected_symptom": expected_symptom,
        "experiments": experiments,
        "min_fidelity": min_fidelity,
        "impact": impact,
        "decision_relevance": decision_relevance,
    }


SIGNATURES = [
    _sig("resource_lifecycle",
         _trait_match(frozenset({"dep-class:pool", "code-touch:connection", "cfg-class:pool"})),
         ["connection_cycles", "requests"],
         "positive_persistent_growth:open_handles",
         ["signal:growth_projection", "probe:resource_lifecycle_v1"],
         {"input_shape": 0.6, "state_representativeness": 0.3},
         "high", 0.9),
    _sig("rate_balance",
         _trait_match(frozenset({"cfg-class:retry", "code-touch:retry",
                                 "cfg-class:queue", "cfg-class:batch"})),
         ["retries", "requests"],
         "sustained_positive_drift:queue_depth",
         ["signal:queue_drift_projection", "probe:rate_balance_v1"],
         {"input_shape": 0.6, "dependency_behavior": 0.5},
         "high", 0.85),
    # Deliberately no signal experiment: expiry bugs are event-sequence-only.
    _sig("clock_expiry",
         _trait_match(frozenset({"dep-class:auth", "cfg-class:ttl",
                                 "cfg-class:expiry", "code-touch:auth"})),
         ["expiry_events", "connection_cycles"],
         "stale_credential_reuse_after_rotation",
         ["probe:cred_lifecycle_v1"],
         {"clock_coverage": 0.5, "dependency_behavior": 0.5},
         "high", 0.9),
    # Compiled but unsupported in MVP: no state materialization.
    _sig("state_boundary",
         _trait_match(frozenset({"kind:schema", "cfg-class:cache"})),
         ["state"],
         "divergence_at_state_boundary",
         [], {}, "medium", 0.6),
    # Placeholder trigger for lock/async traits.
    _sig("concurrency",
         _trait_match(frozenset({"code-touch:schedule"})),
         ["schedule"],
         "interleaving_divergence",
         [], {}, "medium", 0.5),
    _sig("agent_longevity",
         _flag_match(("agent", "memory")),
         ["wall_clock"],
         "context_degradation_over_age",
         [], {}, "medium", 0.5),
]


def hazard_id(klass: str, features: list[str], manifest_digest: str) -> str:
    basis = klass + "|" + ",".join(sorted(features)) + "|" + manifest_digest
    return "hz_" + hashlib.sha256(basis.encode()).hexdigest()[:16]


def compile(deploy_event_or_manifest: dict, inventory: dict | None = None) -> list[dict]:
    """Deterministic hazard floor (source "floor") from the manifest traits."""
    feats = _manifest.features(deploy_event_or_manifest)
    mdig = _manifest.digest(deploy_event_or_manifest)
    hazards = []
    for sig in SIGNATURES:
        matched = sig["matched"](feats)
        if not matched:
            continue
        h = {
            "hazard_id": hazard_id(sig["class"], matched, mdig),
            "class": sig["class"],
            "source": "floor",
            "features": matched,
            "age_dimensions": list(sig["age_dimensions"]),
            "expected_symptom": sig["expected_symptom"],
            "experiments": list(sig["experiments"]),
            "min_fidelity": dict(sig["min_fidelity"]),
            "impact": sig["impact"],
            "decision_relevance": sig["decision_relevance"],
            "status": "compiled",
            "manifest_digest": mdig,
        }
        if inventory is not None:
            h["executable_experiments"] = [
                e for e in h["experiments"] if _inventory.executable(e, inventory)]
        hazards.append(h)
    return hazards


def merge_proposals(floor: list[dict], proposals: list[dict]) -> tuple[list[dict], list[dict]]:
    """(merged, rejected). Proposals may only ADD new hazards (source
    "proposed") or RAISE decision_relevance of an existing one; removal or
    downgrade attempts against the floor are ignored and reported."""
    merged = {h["hazard_id"]: dict(h) for h in floor}
    rejected = []
    for p in proposals or []:
        hid = p.get("hazard_id")
        if p.get("action") == "remove" or p.get("status") in ("removed", "dismissed"):
            rejected.append({"proposal": p, "reason": "hazards cannot be removed"})
            continue
        if hid in merged:
            rel = p.get("decision_relevance")
            cur = merged[hid].get("decision_relevance") or 0.0
            if isinstance(rel, (int, float)) and rel > cur:
                merged[hid]["decision_relevance"] = float(rel)
            else:
                rejected.append({"proposal": p,
                                 "reason": "floor relevance can only be raised"})
            continue
        if not hid or p.get("class") not in HAZARD_CLASSES:
            rejected.append({"proposal": p, "reason": "missing hazard_id or unknown class"})
            continue
        h = dict(p)
        h["source"] = "proposed"
        merged[hid] = h
    return list(merged.values()), rejected
