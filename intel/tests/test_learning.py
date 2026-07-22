"""Conservative-learning invariants: labeled support only, recurrence
threshold, contradiction blocking, and correctness attribution."""

import json

from rollout_intel.db import Db
from rollout_intel.dossier import DossierStore
from rollout_intel.learning import signal_utility, suggest_promotions

SVC = "svc://autocloud/checkout-api/prod/us-central1"


def make_db() -> Db:
    db = Db(":memory:")
    db.upsert_service({"service_uid": SVC, "name": "checkout-api", "environment": "prod",
                       "region": "us-central1", "runtime": "cloud-run",
                       "architecture_version": "v1"})
    return db


def add_episode(db: Db, ep_id: str, label: str | None) -> None:
    db.execute(
        """INSERT INTO episodes(episode_id,service_uid,revision_from,revision_to,
           fingerprint_json,deploy_event_json,started_at,status,final_verdict,
           final_label,labeled_at,architecture_version,created_at)
           VALUES(?,?,?,?,'{}','{}','2026-01-01T00:00:00Z','closed',?,?,
                  '2026-01-02T00:00:00Z','v1','2026-01-01T00:00:00Z')""",
        (ep_id, SVC, "r1", "r2",
         "healthy" if label == "healthy" else "regression-suspected", label))


def propose(store: DossierStore, value, sources: list) -> dict:
    return store.propose(SVC, "stabilization_window_minutes", value, "hypothesized",
                         sources=sources, agent_originated=True)


def test_support_counts_only_labeled_episodes():
    db = make_db()
    store = DossierStore(db)
    add_episode(db, "ep_l1", "healthy")
    add_episode(db, "ep_l2", "healthy")
    db.execute("UPDATE episodes SET final_label=NULL WHERE episode_id='ep_l2'")
    propose(store, 15, ["ep_l1", "ep_l2", "ep_unlabeled", "ep_ghost"])
    result = suggest_promotions(db)
    assert result["suggestions"] == []
    assert result["blocked"][0]["support"] == 1  # only ep_l1 counts


def test_recurrence_threshold_and_suggestion():
    db = make_db()
    store = DossierStore(db)
    for i in range(3):
        add_episode(db, f"ep_l{i}", "healthy")
    propose(store, 15, ["ep_l0", "ep_l1"])
    assert suggest_promotions(db)["suggestions"] == []
    propose(store, 15, ["ep_l2"])  # third distinct labeled episode
    result = suggest_promotions(db)
    assert len(result["suggestions"]) == 1
    s = result["suggestions"][0]
    assert s["support"] == 3 and s["value"] == 15
    assert len(s["rev_ids"]) == 2  # both proposals in the winning group


def test_contradiction_blocks_suggestion():
    db = make_db()
    store = DossierStore(db)
    for i in range(4):
        add_episode(db, f"ep_l{i}", "healthy")
    propose(store, 15, ["ep_l0", "ep_l1", "ep_l2"])
    propose(store, 30, ["ep_l3"])  # rival value with labeled support
    result = suggest_promotions(db)
    assert result["suggestions"] == []
    kinds = {b["kind"] for entry in result["blocked"] for b in entry["blocked_by"]}
    assert "rival_proposal" in kinds


def test_active_claim_contradiction_blocks():
    db = make_db()
    store = DossierStore(db)
    for i in range(3):
        add_episode(db, f"ep_l{i}", "healthy")
    rev = store.propose(SVC, "stabilization_window_minutes", 30, "asserted",
                        agent_originated=False)
    store.activate(rev["rev_id"], "op")
    propose(store, 15, ["ep_l0", "ep_l1", "ep_l2"])
    result = suggest_promotions(db)
    assert result["suggestions"] == []
    assert result["blocked"][0]["blocked_by"][0]["kind"] == "active_claim"


def _record_decision(db: Db, ep_id: str, verdict: str, inputs: dict) -> None:
    cp = db.open_checkpoint(ep_id, "T+5", "ses_test", "2026-01-01T00:00:00Z")
    db.insert_decision(cp["checkpoint_id"], "stage_verdict",
                       {"stage_verdict": verdict}, inputs)


def test_signal_utility_attributes_correctness():
    db = make_db()
    add_episode(db, "ep_good", "healthy")       # verdict healthy -> correct
    add_episode(db, "ep_bad", "regressed")      # verdict healthy -> false safe
    db.execute("""INSERT INTO observations(observation_id,episode_id,checkpoint_id,type,
                  scope_json,observed_at,fresh_until,source,payload_json,quality_json,
                  content_hash,sig_verified,recorded_at)
                  VALUES('obs_m','ep_good','cp','metric_window','{}','t','t','s','{}','{}','h',1,'t')""")
    _record_decision(db, "ep_good", "healthy",
                     {"observation_ids": ["obs_m"], "policy_rule_ids": ["p99-envelope"],
                      "dossier_fields_used": ["p99_baseline_ms"],
                      "precedent_episode_ids": ["fx_ep_001"]})
    _record_decision(db, "ep_bad", "healthy",
                     {"observation_ids": [], "policy_rule_ids": ["p99-envelope"],
                      "dossier_fields_used": [], "precedent_episode_ids": []})
    result = signal_utility(db)
    assert result["scored_decisions"] == 2
    rule = next(r for r in result["policy_rules"] if r["signal"] == "p99-envelope")
    assert rule["correct"] == 1 and rule["incorrect"] == 1 and rule["utility"] == 0.5
    obs = next(o for o in result["observation_types"] if o["signal"] == "metric_window")
    assert obs["correct"] == 1 and obs["incorrect"] == 0
    assert result["precedent_use"] == {"correct": 1, "incorrect": 0}


def test_signal_utility_skips_abstentions():
    db = make_db()
    add_episode(db, "ep_thin", "healthy")
    _record_decision(db, "ep_thin", "insufficient-evidence", {})
    result = signal_utility(db)
    assert result["scored_decisions"] == 0
    assert result["abstentions_skipped"] == 1
