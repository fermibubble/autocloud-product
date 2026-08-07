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

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Db, row_dict
from .models import Checkpoint, Decision, DossierRevision, Episode, Observation

MIN_SUPPORT = 3

UNHEALTHY = ("regressed", "rolled_back")


def _labeled_before(s: Session, recorded_at: str) -> set[str]:
    """Episodes that were ALREADY labeled when a proposal was recorded.
    Citing in-flight episodes that happen to get labeled later does not
    count — support must come from ground truth that existed at proposal
    time, so recurrence means re-proposing as evidence accumulates. Note
    labels prove the cited episodes are ground-truthed; whether they
    AGREE with the claim is the human promoter's judgment."""
    return set(s.execute(
        select(Episode.episode_id)
        .where(Episode.final_label.is_not(None),
               Episode.labeled_at <= recorded_at)
    ).scalars())


def suggest_promotions(db: Db) -> dict:
    with db.session() as s:
        proposals = [row_dict(p) for p in s.execute(
            select(DossierRevision)
            .where(DossierRevision.status == "proposed")
            .order_by(DossierRevision.recorded_at)
        ).scalars()]

        # Group rival proposals by (service, field); support groups by value.
        by_field: dict[tuple, dict[str, dict]] = defaultdict(dict)
        for p in proposals:
            key = (p["service_uid"], p["field"])
            group = by_field[key].setdefault(p["value_json"], {
                "rev_ids": [], "support": set(), "epistemic_types": set()})
            group["rev_ids"].append(p["rev_id"])
            group["epistemic_types"].add(p["epistemic_type"])
            labeled = _labeled_before(s, p["recorded_at"])
            for src in json.loads(p["sources_json"] or "[]"):
                if isinstance(src, str) and src in labeled:
                    group["support"].add(src)

        suggestions, blocked = [], []
        for (service_uid, field), groups in by_field.items():
            active = s.execute(
                select(DossierRevision)
                .where(DossierRevision.service_uid == service_uid,
                       DossierRevision.field == field,
                       DossierRevision.status == "active")
            ).scalars().first()
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
                if active and active.value_json != value_json:
                    contradictions.append(
                        {"kind": "active_claim", "rev_id": active.rev_id,
                         "value": json.loads(active.value_json)})
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
    obs_types: dict[str, dict] = defaultdict(lambda: {"correct": 0, "incorrect": 0})
    rules: dict[str, dict] = defaultdict(lambda: {"correct": 0, "incorrect": 0})
    fields: dict[str, dict] = defaultdict(lambda: {"correct": 0, "incorrect": 0})
    precedent_use = {"correct": 0, "incorrect": 0}
    scored = skipped = 0

    with db.session() as s:
        rows = s.execute(
            select(Decision.value_json, Decision.inputs_json,
                   Episode.final_label, Episode.episode_id)
            .join(Checkpoint, Checkpoint.checkpoint_id == Decision.checkpoint_id)
            .join(Episode, Episode.episode_id == Checkpoint.episode_id)
            .where(Decision.kind == "stage_verdict",
                   Episode.final_label.is_not(None))
        ).all()

        for value_json, inputs_json, final_label, _episode_id in rows:
            value = json.loads(value_json or "{}")
            verdict = value.get("stage_verdict") or value.get("rejected_verdict")
            if verdict in (None, "insufficient-evidence"):
                skipped += 1  # abstentions are scored elsewhere (decision quality)
                continue
            bad = final_label in UNHEALTHY
            correct = (verdict == "regression-suspected") == bad
            bucket = "correct" if correct else "incorrect"
            scored += 1

            inputs = json.loads(inputs_json or "{}")
            obs_ids = [o for o in inputs.get("observation_ids", []) if o]
            if obs_ids:
                for obs_type in s.execute(
                        select(Observation.type).distinct()
                        .where(Observation.observation_id.in_(obs_ids))
                ).scalars():
                    obs_types[obs_type][bucket] += 1
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
