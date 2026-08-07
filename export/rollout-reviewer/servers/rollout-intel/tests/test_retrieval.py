"""find_precedents hard-filter basics against a real tmp-SQLite Db:
labeled-only candidates, bitemporal as_of, exclude_episode."""

import pytest
from sqlalchemy import update

from rollout_intel.db import Db
from rollout_intel.models import Episode
from rollout_intel.retrieval import find_precedents

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
    d = Db(str(tmp_path / "episodes.db"))
    d.upsert_service(dict(SVC))
    return d


def _labeled_episode(db: Db, label: str, labeled_at: str) -> str:
    ep = db.create_episode(SVC["service_uid"], FP, DEPLOY)
    with db.session() as s:
        s.execute(update(Episode)
                  .where(Episode.episode_id == ep["episode_id"])
                  .values(final_label=label, labeled_at=labeled_at,
                          status="closed", final_verdict="healthy"))
    return ep["episode_id"]


def _returned_ids(result: dict) -> set[str]:
    return {p["episode_id"] for p in result["healthy"] + result["unhealthy"]}


def test_precedents_are_labeled_episodes_only(db):
    healthy = {_labeled_episode(db, "healthy", "2026-01-01T00:00:00Z")
               for _ in range(2)}
    unhealthy = {_labeled_episode(db, "regressed", "2026-01-01T00:00:00Z"),
                 _labeled_episode(db, "rolled_back", "2026-01-01T00:00:00Z")}
    # Unlabeled episode carrying only the agent's own verdict: never precedent.
    verdict_only = db.create_episode(SVC["service_uid"], FP, DEPLOY)
    with db.session() as s:
        s.execute(update(Episode)
                  .where(Episode.episode_id == verdict_only["episode_id"])
                  .values(final_verdict="healthy", status="awaiting_outcome"))

    result = find_precedents(db, SVC, FP)
    assert verdict_only["episode_id"] not in _returned_ids(result)
    assert {p["episode_id"] for p in result["healthy"]} == healthy
    assert {p["episode_id"] for p in result["unhealthy"]} == unhealthy
    assert result["insufficient_precedent"] is False


def test_as_of_excludes_episodes_labeled_later(db):
    ep = _labeled_episode(db, "healthy", "2026-02-01T00:00:00Z")
    # Replay from before the label existed: the episode is invisible.
    before = find_precedents(db, SVC, FP, as_of="2026-01-15T00:00:00Z")
    assert ep not in _returned_ids(before)
    assert before["healthy"] == []
    assert before["insufficient_precedent"] is True
    # Once the label exists at as_of, it is a candidate.
    after = find_precedents(db, SVC, FP, as_of="2026-02-02T00:00:00Z")
    assert ep in _returned_ids(after)


def test_exclude_episode_is_honored(db):
    a = _labeled_episode(db, "healthy", "2026-01-01T00:00:00Z")
    b = _labeled_episode(db, "healthy", "2026-01-01T00:00:00Z")
    without = find_precedents(db, SVC, FP)
    assert {a, b} <= _returned_ids(without)
    excluded = find_precedents(db, SVC, FP, exclude_episode=a)
    assert a not in _returned_ids(excluded)
    assert b in _returned_ids(excluded)
