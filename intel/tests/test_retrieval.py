"""Precedent retrieval invariants: labeled-only, bitemporal, balanced,
architecture-compatible, widening only when starved."""

import json

from rollout_intel.db import Db
from rollout_intel.retrieval import find_precedents

SVC = "svc://autocloud/checkout-api/prod/us-central1"
PEER = "svc://autocloud/checkout-worker/prod/us-central1"


def fp(**over) -> dict:
    base = {"fingerprint_version": "v1", "service_family": "checkout",
            "runtime": "cloud-run", "environment": "prod",
            "architecture_version": "v1", "strategy": "canary",
            "change_classes": ["application_binary"], "image_digest": "sha256:x"}
    base.update(over)
    return base


def make_db() -> Db:
    db = Db(":memory:")
    for uid, name in ((SVC, "checkout-api"), (PEER, "checkout-worker")):
        db.upsert_service({"service_uid": uid, "name": name, "environment": "prod",
                           "region": "us-central1", "runtime": "cloud-run",
                           "architecture_version": "v1"})
    return db


def add_episode(db: Db, ep_id: str, uid: str, label: str | None, labeled_at: str | None,
                verdict: str = "healthy", fingerprint: dict | None = None,
                arch: str = "v1") -> None:
    db.execute(
        """INSERT INTO episodes(episode_id,service_uid,revision_from,revision_to,
           fingerprint_json,deploy_event_json,started_at,status,final_verdict,
           final_label,labeled_at,architecture_version,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ep_id, uid, "r1", "r2", json.dumps(fingerprint or fp(architecture_version=arch)),
         "{}", "2026-01-01T00:00:00Z", "closed" if label else "awaiting_outcome",
         verdict, label, labeled_at, arch, "2026-01-01T00:00:00Z"))


def svc_row(db: Db) -> dict:
    return db.one("SELECT * FROM services WHERE service_uid=?", (SVC,))


def test_unlabeled_episodes_are_never_precedents():
    db = make_db()
    add_episode(db, "ep_unlabeled", SVC, None, None)  # agent verdict only
    result = find_precedents(db, svc_row(db), fp())
    assert result["healthy"] == [] and result["unhealthy"] == []
    assert result["insufficient_precedent"] is True


def test_bitemporal_as_of_excludes_future_labels():
    db = make_db()
    add_episode(db, "ep_old", SVC, "healthy", "2026-02-01T00:00:00Z")
    add_episode(db, "ep_future", SVC, "healthy", "2026-06-01T00:00:00Z")
    result = find_precedents(db, svc_row(db), fp(), as_of="2026-03-01T00:00:00Z")
    ids = [p["episode_id"] for p in result["healthy"]]
    assert ids == ["ep_old"]


def test_balance_never_backfills():
    db = make_db()
    for i in range(5):
        add_episode(db, f"ep_h{i}", SVC, "healthy", f"2026-02-0{i + 1}T00:00:00Z")
    result = find_precedents(db, svc_row(db), fp())
    assert len(result["healthy"]) == 2          # capped
    assert result["unhealthy"] == []            # not padded with healthy
    assert result["insufficient_precedent"] is True


def test_balanced_two_plus_two():
    db = make_db()
    for i in range(3):
        add_episode(db, f"ep_h{i}", SVC, "healthy", f"2026-02-0{i + 1}T00:00:00Z")
        add_episode(db, f"ep_u{i}", SVC, "regressed", f"2026-02-0{i + 1}T12:00:00Z",
                    verdict="regression-suspected")
    result = find_precedents(db, svc_row(db), fp())
    assert len(result["healthy"]) == 2 and len(result["unhealthy"]) == 2
    assert result["insufficient_precedent"] is False
    assert result["scope_rung"] == "service"


def test_architecture_incompatible_is_history_not_precedent():
    db = make_db()
    add_episode(db, "ep_v1", SVC, "healthy", "2026-02-01T00:00:00Z", arch="v1")
    add_episode(db, "ep_v2", SVC, "healthy", "2026-02-02T00:00:00Z", arch="v2")
    result = find_precedents(db, svc_row(db), fp(architecture_version="v1"))
    ids = [p["episode_id"] for p in result["healthy"]]
    assert "ep_v2" not in ids and "ep_v1" in ids


def test_widening_to_family_when_service_starved():
    db = make_db()
    add_episode(db, "ep_self", SVC, "healthy", "2026-02-01T00:00:00Z")
    for i in range(2):
        add_episode(db, f"ep_peer_h{i}", PEER, "healthy", f"2026-02-0{i + 2}T00:00:00Z")
        add_episode(db, f"ep_peer_u{i}", PEER, "rolled_back", f"2026-02-0{i + 2}T12:00:00Z",
                    verdict="regression-suspected")
    result = find_precedents(db, svc_row(db), fp())
    assert result["scope_rung"] == "family"
    all_ids = [p["episode_id"] for p in result["healthy"] + result["unhealthy"]]
    assert len(all_ids) == 4


def test_similarity_ranks_within_label_group():
    db = make_db()
    add_episode(db, "ep_close", SVC, "regressed", "2026-02-01T00:00:00Z",
                fingerprint=fp(change_classes=["application_binary"]))
    add_episode(db, "ep_far", SVC, "regressed", "2026-02-02T00:00:00Z",
                fingerprint=fp(strategy="all-at-once",
                               change_classes=["infra", "schema", "flags"]))
    add_episode(db, "ep_far2", SVC, "regressed", "2026-02-03T00:00:00Z",
                fingerprint=fp(strategy="blue-green", change_classes=["infra"]))
    result = find_precedents(db, svc_row(db), fp())
    assert result["unhealthy"][0]["episode_id"] == "ep_close"


def test_every_retrieval_is_audited():
    db = make_db()
    add_episode(db, "ep_h", SVC, "healthy", "2026-02-01T00:00:00Z")
    find_precedents(db, svc_row(db), fp(), episode_id="ep_current", tool="test-tool")
    audits = db.query("SELECT * FROM retrieval_audit WHERE tool='test-tool'")
    assert len(audits) == 1
    assert json.loads(audits[0]["returned_ids_json"]) == ["ep_h"]
    # A starved corpus widens through every rung; the audit records the
    # rung actually used, not the rung we wish had sufficed.
    assert json.loads(audits[0]["filters_json"])["scope_rung"] == "runtime"
