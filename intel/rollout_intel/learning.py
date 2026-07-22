"""Conservative learning (research §10): the machine SUGGESTS, the human
promotes. Nothing in this module writes a dossier revision or a memory —
it only reads labeled history and surfaces:

  1. Promotion suggestions — a proposed dossier claim earns a suggestion
     only with support from >= MIN_SUPPORT distinct LABELED episodes
     (agent-verdict-only episodes never count) AND no contradiction: no
     active claim with a different value for the field, and no rival
     proposal group with labeled support of its own. A contradicted claim
     is reported as blocked, with the contradiction, not hidden.

  2. Signal utility — which observation types, policy rules, dossier
     fields, and precedents actually appeared in decisions that turned
     out CORRECT vs INCORRECT against later labels. This is the
     evidence-pruning input for dynamic bundles; it makes no decisions
     itself.
"""

import json
from collections import defaultdict

from .db import Db

MIN_SUPPORT = 3

UNHEALTHY = ("regressed", "rolled_back")


def _labeled_before(db: Db, recorded_at: str) -> set[str]:
    """Episodes that were ALREADY labeled when a proposal was recorded.
    Citing in-flight episodes that happen to get labeled later does not
    count — support must come from ground truth that existed at proposal
    time, so recurrence means re-proposing as evidence accumulates. Note
    labels prove the cited episodes are ground-truthed; whether they
    AGREE with the claim is the human promoter's judgment."""
    return {r["episode_id"] for r in
            db.query("SELECT episode_id FROM episodes "
                     "WHERE final_label IS NOT NULL AND labeled_at <= ?",
                     (recorded_at,))}


def suggest_promotions(db: Db) -> dict:
    proposals = db.query(
        "SELECT * FROM dossier_journal WHERE status='proposed' ORDER BY recorded_at")

    # Group rival proposals by (service, field); support groups by value.
    by_field: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for p in proposals:
        key = (p["service_uid"], p["field"])
        group = by_field[key].setdefault(p["value_json"], {
            "rev_ids": [], "support": set(), "epistemic_types": set()})
        group["rev_ids"].append(p["rev_id"])
        group["epistemic_types"].add(p["epistemic_type"])
        labeled = _labeled_before(db, p["recorded_at"])
        for src in json.loads(p["sources_json"] or "[]"):
            if isinstance(src, str) and src in labeled:
                group["support"].add(src)

    suggestions, blocked = [], []
    for (service_uid, field), groups in by_field.items():
        active = db.one(
            """SELECT value_json, rev_id FROM dossier_journal
               WHERE service_uid=? AND field=? AND status='active'""",
            (service_uid, field))
        for value_json, group in groups.items():
            support = sorted(group["support"])
            entry = {
                "service_uid": service_uid, "field": field,
                "value": json.loads(value_json),
                "rev_ids": group["rev_ids"],
                "support_episodes": support,
                "support": len(support),
            }
            contradictions = []
            if active and active["value_json"] != value_json:
                contradictions.append(
                    {"kind": "active_claim", "rev_id": active["rev_id"],
                     "value": json.loads(active["value_json"])})
            for rival_value, rival in groups.items():
                if rival_value != value_json and rival["support"]:
                    contradictions.append(
                        {"kind": "rival_proposal",
                         "value": json.loads(rival_value),
                         "support": len(rival["support"])})
            if len(support) >= MIN_SUPPORT and not contradictions:
                suggestions.append(entry)
            else:
                entry["blocked_by"] = (
                    contradictions if contradictions
                    else [{"kind": "insufficient_support",
                           "need": MIN_SUPPORT, "have": len(support)}])
                blocked.append(entry)

    return {"suggestions": suggestions, "blocked": blocked,
            "note": ("Suggestions are promotion CANDIDATES: a human still "
                     "promotes via intelctl (which stamps verified_by). "
                     "Support counts only labeled episodes.")}


def signal_utility(db: Db) -> dict:
    """Correctness attribution over labeled episodes' recorded decisions."""
    rows = db.query(
        """SELECT d.value_json, d.inputs_json, e.final_label, e.episode_id
           FROM decisions d
           JOIN checkpoints c ON c.checkpoint_id = d.checkpoint_id
           JOIN episodes e ON e.episode_id = c.episode_id
           WHERE d.kind='stage_verdict' AND e.final_label IS NOT NULL""")

    obs_types: dict[str, dict] = defaultdict(lambda: {"correct": 0, "incorrect": 0})
    rules: dict[str, dict] = defaultdict(lambda: {"correct": 0, "incorrect": 0})
    fields: dict[str, dict] = defaultdict(lambda: {"correct": 0, "incorrect": 0})
    precedent_use = {"correct": 0, "incorrect": 0}
    scored = skipped = 0

    for row in rows:
        value = json.loads(row["value_json"] or "{}")
        verdict = value.get("stage_verdict") or value.get("rejected_verdict")
        if verdict in (None, "insufficient-evidence"):
            skipped += 1  # abstentions are scored elsewhere (decision quality)
            continue
        bad = row["final_label"] in UNHEALTHY
        correct = (verdict == "regression-suspected") == bad
        bucket = "correct" if correct else "incorrect"
        scored += 1

        inputs = json.loads(row["inputs_json"] or "{}")
        obs_ids = [o for o in inputs.get("observation_ids", []) if o]
        if obs_ids:
            placeholders = ",".join("?" for _ in obs_ids)
            for o in db.query(
                    f"SELECT DISTINCT type FROM observations WHERE observation_id IN ({placeholders})",
                    tuple(obs_ids)):
                obs_types[o["type"]][bucket] += 1
        for rule in inputs.get("policy_rule_ids", []):
            rules[rule][bucket] += 1
        for field in inputs.get("dossier_fields_used", []):
            fields[field][bucket] += 1
        if inputs.get("precedent_episode_ids"):
            precedent_use[bucket] += 1

    def ranked(counter: dict) -> list[dict]:
        out = []
        for name, c in counter.items():
            total = c["correct"] + c["incorrect"]
            out.append({"signal": name, **c,
                        "utility": round(c["correct"] / total, 3) if total else None})
        out.sort(key=lambda s: (-(s["utility"] or 0), -s["correct"]))
        return out

    return {
        "scored_decisions": scored, "abstentions_skipped": skipped,
        "observation_types": ranked(obs_types),
        "policy_rules": ranked(rules),
        "dossier_fields": ranked(fields),
        "precedent_use": precedent_use,
        "note": ("Utility ranks which signals appeared in decisions later "
                 "proven correct; it prunes evidence bundles, it never "
                 "overrides policy."),
    }
