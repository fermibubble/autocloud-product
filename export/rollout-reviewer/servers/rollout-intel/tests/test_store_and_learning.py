"""Store lifecycle + conservative-learning invariants, against a real
tmp-SQLite Db. No mocks: every test opens its own database file."""

import json

import pytest
from sqlalchemy import select, update

from rollout_intel.db import Db
from rollout_intel.learning import signal_utility, suggest_promotions
from rollout_intel.models import Checkpoint, DossierRevision, Episode, Observation

FP = {
    "fingerprint_version": "v1",
    "service_family": "checkout",
    "runtime": "cloud-run",
    "environment": "prod",
    "architecture_version": "v1",
    "strategy": "canary",
    "change_classes": ["code"],
    "image_digest": "sha256:abc",
}

DEPLOY = {"from_revision": "r1", "to_revision": "r2", "strategy": "canary"}

SVC = {
    "service_uid": "svc-checkout-prod",
    "name": "checkout-prod",
    "environment": "prod",
    "region": "us-east1",
    "runtime": "cloud-run",
    "architecture_version": "v1",
    "owner": "team-payments",
}


@pytest.fixture()
def db(tmp_path):
    return Db(str(tmp_path / "episodes.db"))


def _episode(db: Db) -> dict:
    db.upsert_service(dict(SVC))
    return db.create_episode(SVC["service_uid"], FP, DEPLOY)


def _label(db: Db, episode_id: str, label: str, labeled_at: str) -> None:
    """Tests stand in for the outcome collector: stamp ground truth."""
    with db.session() as s:
        s.execute(
            update(Episode)
            .where(Episode.episode_id == episode_id)
            .values(final_label=label, labeled_at=labeled_at, status="closed"))


def _episode_row(db: Db, episode_id: str) -> Episode:
    with db.session() as s:
        return s.get(Episode, episode_id)


# --- episodes / checkpoints -----------------------------------------------


def test_create_episode_opens_with_service_architecture(db):
    ep = _episode(db)
    assert ep["status"] == "open"
    assert ep["architecture_version"] == "v1"
    assert ep["revision_to"] == "r2"
    assert json.loads(ep["fingerprint_json"]) == FP


def test_open_checkpoint_rearms_same_open_row_with_new_session(db):
    ep = _episode(db)
    first = db.open_checkpoint(ep["episode_id"], "1h", "sess-a", "2026-01-01T01:00:00Z")
    # Same (episode, stage) opened again — e.g. clock layer died and retried
    # with a fresh session. Must re-arm the SAME row, not trip UNIQUE.
    second = db.open_checkpoint(ep["episode_id"], "1h", "sess-b", "2026-01-01T01:05:00Z")
    assert second["checkpoint_id"] == first["checkpoint_id"]
    assert second["session_id"] == "sess-b"
    assert second["scheduled_at"] == "2026-01-01T01:05:00Z"
    with db.session() as s:
        rows = s.execute(
            select(Checkpoint).where(Checkpoint.episode_id == ep["episode_id"])
        ).scalars().all()
    assert len(rows) == 1


def test_open_checkpoint_moves_episode_to_in_progress(db):
    ep = _episode(db)
    db.open_checkpoint(ep["episode_id"], "1h", "sess-a", "2026-01-01T01:00:00Z")
    assert _episode_row(db, ep["episode_id"]).status == "in_progress"


def test_complete_checkpoint_completes_once_only(db):
    ep = _episode(db)
    cp = db.open_checkpoint(ep["episode_id"], "1h", "sess-a", "2026-01-01T01:00:00Z")
    done = db.complete_checkpoint(cp["checkpoint_id"], "healthy", "pass", "pol-1",
                                  False, "# report", "2026-01-01T06:00:00Z")
    assert done is not None
    assert done["stage_verdict"] == "healthy"
    assert done["completed_at"] is not None
    # Second completion lost the race: None, and the first result stands.
    again = db.complete_checkpoint(cp["checkpoint_id"], "regression-suspected",
                                   "fail", "pol-1", False, "# other", None)
    assert again is None
    with db.session() as s:
        row = s.get(Checkpoint, cp["checkpoint_id"])
    assert row.stage_verdict == "healthy"
    assert row.report_md == "# report"


def test_complete_with_next_check_keeps_episode_in_progress(db):
    ep = _episode(db)
    cp = db.open_checkpoint(ep["episode_id"], "1h", "sess-a", "2026-01-01T01:00:00Z")
    db.complete_checkpoint(cp["checkpoint_id"], "healthy", "pass", "pol-1",
                           False, "# report", "2026-01-01T06:00:00Z")
    assert _episode_row(db, ep["episode_id"]).status == "in_progress"


def test_complete_without_next_check_closes_episode_to_awaiting_outcome(db):
    ep = _episode(db)
    cp = db.open_checkpoint(ep["episode_id"], "24h", "sess-a", "2026-01-02T00:00:00Z")
    db.complete_checkpoint(cp["checkpoint_id"], "healthy", "pass", "pol-1",
                           False, "# final", None)
    row = _episode_row(db, ep["episode_id"])
    assert row.status == "awaiting_outcome"
    assert row.final_verdict == "healthy"


def test_report_version_monotonic_across_episode_checkpoints(db):
    ep = _episode(db)
    versions = []
    for i, stage in enumerate(("1h", "6h", "24h")):
        cp = db.open_checkpoint(ep["episode_id"], stage, f"sess-{i}",
                                f"2026-01-01T0{i + 1}:00:00Z")
        last = stage == "24h"
        done = db.complete_checkpoint(
            cp["checkpoint_id"], "healthy", "pass", "pol-1", False, "# r",
            None if last else f"2026-01-01T0{i + 2}:00:00Z")
        versions.append(done["report_version"])
    assert versions == [1, 2, 3]


# --- observations ----------------------------------------------------------


def test_insert_observation_idempotent_on_observation_id(db):
    ep = _episode(db)
    cp = db.open_checkpoint(ep["episode_id"], "1h", "sess-a", "2026-01-01T01:00:00Z")
    env = {"observation_id": "obs_fixed", "type": "metrics",
           "payload": {"error_rate": 0.1}, "source": "prometheus"}
    db.insert_observation(ep["episode_id"], cp["checkpoint_id"], env, verified=True)
    # Same envelope re-presented with drifted content: first write wins.
    drifted = {"observation_id": "obs_fixed", "type": "logs",
               "payload": {"error_rate": 9.9}, "source": "elsewhere"}
    db.insert_observation(ep["episode_id"], cp["checkpoint_id"], drifted, verified=False)
    with db.session() as s:
        rows = s.execute(select(Observation)).scalars().all()
    assert len(rows) == 1
    assert rows[0].type == "metrics"
    assert json.loads(rows[0].payload_json) == {"error_rate": 0.1}
    assert rows[0].sig_verified == 1


# --- services --------------------------------------------------------------


def test_upsert_service_sparse_update_preserves_absent_fields(db):
    db.upsert_service(dict(SVC))
    # Sparse entry: only owner present — runtime/architecture must survive.
    db.upsert_service({"service_uid": SVC["service_uid"], "owner": "team-new"})
    with db.session() as s:
        from rollout_intel.models import Service
        row = s.get(Service, SVC["service_uid"])
    assert row.owner == "team-new"
    assert row.runtime == "cloud-run"
    assert row.architecture_version == "v1"
    assert row.name == "checkout-prod"


# --- learning: the agent never learns from its own verdicts ----------------


def _proposal(db: Db, rev_id: str, sources: list[str], recorded_at: str,
              field: str = "known_failure_mode", value: str = '"cold-start"') -> None:
    with db.session() as s:
        s.add(DossierRevision(
            rev_id=rev_id, service_uid=SVC["service_uid"], field=field,
            value_json=value, epistemic_type="observed", status="proposed",
            recorded_at=recorded_at, sources_json=json.dumps(sources)))


def test_suggestions_count_only_labeled_episodes_as_support(db):
    labeled = _episode(db)
    unlabeled = db.create_episode(SVC["service_uid"], FP, DEPLOY)
    _label(db, labeled["episode_id"], "regressed", "2026-01-01T00:00:00Z")
    # unlabeled has a final_verdict (the agent's own conclusion) but no label.
    with db.session() as s:
        s.execute(update(Episode)
                  .where(Episode.episode_id == unlabeled["episode_id"])
                  .values(final_verdict="regression-suspected"))
    _proposal(db, "rev_1",
              [labeled["episode_id"], unlabeled["episode_id"]],
              "2026-01-02T00:00:00Z")

    out = suggest_promotions(db)
    assert out["suggestions"] == []
    (entry,) = out["blocked"]
    # The unlabeled episode contributed nothing, verdict or not.
    assert entry["support_episodes"] == [labeled["episode_id"]]
    assert entry["support"] == 1
    assert entry["blocked_by"] == [
        {"kind": "insufficient_support", "need": 3, "have": 1}]


def test_three_labeled_supporters_yield_suggestion_but_verdicts_never_do(db):
    db.upsert_service(dict(SVC))
    labeled_ids = []
    for i in range(3):
        ep = db.create_episode(SVC["service_uid"], FP, DEPLOY)
        _label(db, ep["episode_id"], "regressed", "2026-01-01T00:00:00Z")
        labeled_ids.append(ep["episode_id"])
    unlabeled = db.create_episode(SVC["service_uid"], FP, DEPLOY)
    # Positive control: 3 labeled sources → suggested.
    _proposal(db, "rev_ok", labeled_ids, "2026-01-02T00:00:00Z")
    # 2 labeled + 1 agent-verdict-only source → still blocked.
    _proposal(db, "rev_short", labeled_ids[:2] + [unlabeled["episode_id"]],
              "2026-01-02T00:00:00Z", field="scaling_quirk", value='"slow-warm"')

    out = suggest_promotions(db)
    assert [e["field"] for e in out["suggestions"]] == ["known_failure_mode"]
    assert out["suggestions"][0]["support"] == 3
    (short,) = out["blocked"]
    assert short["field"] == "scaling_quirk"
    assert short["support"] == 2
    assert unlabeled["episode_id"] not in short["support_episodes"]


def test_signal_utility_scores_only_labeled_episodes(db):
    labeled = _episode(db)
    lcp = db.open_checkpoint(labeled["episode_id"], "1h", "s1", "2026-01-01T01:00:00Z")
    db.insert_observation(labeled["episode_id"], lcp["checkpoint_id"],
                          {"observation_id": "obs_l", "type": "metrics"}, True)
    db.insert_decision(lcp["checkpoint_id"], "stage_verdict",
                       {"stage_verdict": "regression-suspected"},
                       {"observation_ids": ["obs_l"],
                        "policy_rule_ids": ["rule_labeled"],
                        "dossier_fields_used": ["field_labeled"],
                        "precedent_episode_ids": ["ep_other"]})
    _label(db, labeled["episode_id"], "regressed", "2026-01-02T00:00:00Z")

    unlabeled = db.create_episode(SVC["service_uid"], FP, DEPLOY)
    ucp = db.open_checkpoint(unlabeled["episode_id"], "1h", "s2", "2026-01-01T01:00:00Z")
    db.insert_observation(unlabeled["episode_id"], ucp["checkpoint_id"],
                          {"observation_id": "obs_u", "type": "logs"}, True)
    db.insert_decision(ucp["checkpoint_id"], "stage_verdict",
                       {"stage_verdict": "healthy"},
                       {"observation_ids": ["obs_u"],
                        "policy_rule_ids": ["rule_unlabeled"],
                        "dossier_fields_used": ["field_unlabeled"],
                        "precedent_episode_ids": ["ep_other"]})

    out = signal_utility(db)
    assert out["scored_decisions"] == 1
    assert out["abstentions_skipped"] == 0
    # regression-suspected against a 'regressed' label is correct.
    assert out["policy_rules"] == [
        {"signal": "rule_labeled", "correct": 1, "incorrect": 0, "utility": 1.0}]
    assert [o["signal"] for o in out["observation_types"]] == ["metrics"]
    assert [f["signal"] for f in out["dossier_fields"]] == ["field_labeled"]
    assert out["precedent_use"] == {"correct": 1, "incorrect": 0}
