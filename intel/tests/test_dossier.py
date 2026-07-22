"""Dossier journal semantics: governed lifecycle, bitemporal reads,
architecture invalidation, and the read-only projection contract."""

import time

from rollout_intel.db import Db
from rollout_intel.dossier import DossierStore, MemoryProjector, topic_for

SVC = "svc://autocloud/demo-healthy/prod/us-central1"


class RecordingProjector(MemoryProjector):
    """Captures projection/retraction calls instead of hitting the gateway."""

    def __init__(self):
        super().__init__(api_base="http://unused", token="unused")
        self.projected: list[dict] = []
        self.retracted: list[str] = []

    def project(self, rev: dict) -> str | None:
        self.projected.append(rev)
        return f"mem_{len(self.projected)}"

    def retract(self, memory_id: str) -> bool:
        self.retracted.append(memory_id)
        return True


def make_store():
    projector = RecordingProjector()
    return DossierStore(Db(":memory:"), projector), projector


def test_agent_cannot_propose_governed_epistemic_types():
    store, _ = make_store()
    for etype in ("approved", "observed", "inferred"):
        rev = store.propose(SVC, "p99_baseline_ms", 180, etype, agent_originated=True)
        assert "error" in rev, etype
    ok = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized", agent_originated=True)
    assert ok["status"] == "proposed"


def test_proposal_is_never_live_until_promoted():
    store, projector = make_store()
    rev = store.propose(SVC, "stabilization_window_minutes", 15, "hypothesized")
    assert store.get(SVC)["claims"] == []
    assert projector.projected == []

    active = store.activate(rev["rev_id"], "sre-oncall", epistemic_type="observed")
    assert active["status"] == "active"
    assert active["epistemic_type"] == "observed"
    assert active["owner_verified_by"] == "sre-oncall"
    claims = store.get(SVC)["claims"]
    assert [c["value"] for c in claims] == [15]
    assert len(projector.projected) == 1
    assert active["memory_id"] == "mem_1"


def test_supersession_and_as_of_time_travel():
    store, _ = make_store()
    r1 = store.propose(SVC, "p99_baseline_ms", 180, "asserted")
    store.activate(r1["rev_id"], "op")
    t_between = None
    time.sleep(1.1)  # ISO-second resolution needs distinct timestamps
    t_between = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    time.sleep(1.1)
    r2 = store.propose(SVC, "p99_baseline_ms", 210, "asserted")
    store.activate(r2["rev_id"], "op")

    now_claims = store.get(SVC)["claims"]
    assert [c["value"] for c in now_claims] == [210]
    then_claims = store.get(SVC, as_of=t_between)["claims"]
    assert [c["value"] for c in then_claims] == [180]
    journal = store.journal(SVC)
    assert [r["status"] for r in journal] == ["superseded", "active"]
    assert journal[0]["superseded_by_rev"] == r2["rev_id"]


def test_reject_never_projects():
    store, projector = make_store()
    rev = store.propose(SVC, "traffic_profile", "diurnal", "hypothesized")
    rejected = store.reject(rev["rev_id"], "sre")
    assert rejected["status"] == "rejected"
    assert store.get(SVC)["claims"] == []
    assert projector.projected == []


def test_architecture_change_expires_sensitive_fields_only():
    store, _ = make_store()
    r1 = store.propose(SVC, "p99_baseline_ms", 180, "asserted")
    store.activate(r1["rev_id"], "op")
    r2 = store.propose(SVC, "owner_notes", "checkout team", "asserted")
    store.activate(r2["rev_id"], "op")

    expired = store.invalidate_architecture(SVC, "v2")
    assert expired == 1
    claims = store.get(SVC)["claims"]
    assert [c["field"] for c in claims] == ["owner_notes"]


def test_expiry_sweep_and_expired_activation_guard():
    store, _ = make_store()
    # An already-expired proposal can never activate (review finding).
    stale = store.propose(SVC, "p99_baseline_ms", 170, "asserted",
                          expires_at="2000-01-01T00:00:00Z")
    result = store.activate(stale["rev_id"], "op")
    assert "error" in result and "expired" in result["error"]
    assert store.get(SVC)["claims"] == []

    # A live claim whose expiry passes is swept out of the active view.
    rev = store.propose(SVC, "p99_baseline_ms", 180, "asserted",
                        expires_at="2999-01-01T00:00:00Z")
    store.activate(rev["rev_id"], "op")
    store.db.execute("UPDATE dossier_journal SET expires_at='2000-01-01T00:00:00Z' "
                     "WHERE rev_id=?", (rev["rev_id"],))
    assert store.sweep_expired() == 1
    assert store.get(SVC)["claims"] == []


def test_expired_claim_never_resurrects_in_as_of():
    """Review finding: expiry used to record no deactivation instant, so
    as_of reads after the sweep returned the expired claim — and both it
    and its successor at once."""
    store, _ = make_store()
    r1 = store.propose(SVC, "p99_baseline_ms", 180, "asserted",
                       expires_at="2000-01-01T00:00:00Z")
    store.activate(r1["rev_id"], "op")  # activated despite expiry? no — guard
    # r1 was already expired at activation time, so it never went live.
    assert store.get(SVC)["claims"] == []

    r2 = store.propose(SVC, "p99_baseline_ms", 185, "asserted",
                       expires_at="2999-01-01T00:00:00Z")
    store.activate(r2["rev_id"], "op")
    time.sleep(1.1)
    t_after = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Force-expire r2 by rewriting its expiry into the past, then sweep.
    store.db.execute("UPDATE dossier_journal SET expires_at='2000-01-02T00:00:00Z' "
                     "WHERE rev_id=?", (r2["rev_id"],))
    time.sleep(1.1)
    assert store.sweep_expired() == 1
    # Before the sweep instant r2 was legitimately in force...
    assert [c["value"] for c in store.get(SVC, as_of=t_after)["claims"]] == [185]
    # ...after it, nothing resurrects.
    t_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    time.sleep(1.1)
    assert store.get(SVC, as_of=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))["claims"] == []
    assert t_now  # (t_now retained for debuggability on failure)


def test_expiry_retracts_projection():
    store, projector = make_store()
    rev = store.propose(SVC, "p99_baseline_ms", 180, "asserted",
                        expires_at="2999-01-01T00:00:00Z")
    store.activate(rev["rev_id"], "op")
    assert len(projector.projected) == 1
    store.db.execute("UPDATE dossier_journal SET expires_at='2000-01-01T00:00:00Z' "
                     "WHERE rev_id=?", (rev["rev_id"],))
    store.sweep_expired()
    assert projector.retracted == ["mem_1"]
    journal = store.journal(SVC)
    assert journal[0]["memory_id"] is None and journal[0]["deactivated_at"]


def test_architecture_invalidation_retracts_and_stamps():
    store, projector = make_store()
    rev = store.propose(SVC, "p99_baseline_ms", 180, "asserted")
    store.activate(rev["rev_id"], "op")
    assert store.invalidate_architecture(SVC, "v2") == 1
    assert projector.retracted == ["mem_1"]
    row = store.journal(SVC)[0]
    assert row["status"] == "expired" and row["deactivated_at"]


def test_topic_namespacing_per_service_and_field():
    assert topic_for(SVC, "p99_baseline_ms") == \
        "dossier:demo-healthy.prod.us-central1:p99_baseline_ms"
    other = "svc://autocloud/demo-thin/prod/us-central1"
    assert topic_for(other, "p99_baseline_ms").startswith("dossier:demo-thin.")
