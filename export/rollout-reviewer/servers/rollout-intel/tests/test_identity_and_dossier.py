"""Identity resolution precedence + dossier state-machine tests.

All tests run against a real tmp-file SQLite Db. The only thing stubbed
is the clock (rollout_intel.dossier.now_iso) so bitemporal windows are
deterministic; the MemoryProjector is simply not attached (projector=None
is a supported configuration), so no network is involved.
"""

import yaml

import pytest
from sqlalchemy import select

from rollout_intel import dossier as dossier_mod
from rollout_intel import identity
from rollout_intel.db import Db
from rollout_intel.dossier import DossierStore
from rollout_intel.models import DossierRevision, Service

SVC = "svc://autocloud/checkout/prod/us-east1"
OTHER_SVC = "svc://autocloud/search/prod/us-east1"


@pytest.fixture
def db(tmp_path):
    return Db(str(tmp_path / "intel.db"))


@pytest.fixture
def store(db):
    return DossierStore(db, projector=None)


class FakeClock:
    def __init__(self, t="2026-01-01T00:00:00Z"):
        self.t = t

    def __call__(self):
        return self.t

    def set(self, t):
        self.t = t


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr(dossier_mod, "now_iso", c)
    return c


def write_catalog(tmp_path, services, filename="services.yaml"):
    path = tmp_path / filename
    path.write_text(yaml.safe_dump({"services": services}), encoding="utf-8")
    return str(path)


# --- identity.resolve -----------------------------------------------------


def test_confirmed_catalog_row_outranks_preexisting_inferred_candidate(db, tmp_path):
    # The inferred candidate lands first, from a deploy event that arrived
    # before the catalog knew the service.
    first = identity.resolve(db, {"service": "checkout", "region": "us-east1"})
    assert first["service_uid"] == "svc://inferred/checkout/prod/us-east1"
    assert first["status"] == "candidate"

    # Then the catalog learns it. Tenant "zeta" is chosen deliberately:
    # "svc://zeta/..." sorts AFTER "svc://inferred/..." by uid, so only
    # status precedence (confirmed before candidate) can make it win —
    # plain uid ordering would re-ship the original bug.
    identity.load_catalog(db, write_catalog(tmp_path, [{
        "tenant": "zeta", "name": "checkout", "environment": "prod",
        "region": "us-east1", "owner": "team-payments"}]))

    resolved = identity.resolve(db, {"service": "checkout", "region": "us-east1"})
    assert resolved["service_uid"] == "svc://zeta/checkout/prod/us-east1"
    assert resolved["status"] == "confirmed"
    assert resolved["source"] == "catalog"


def test_alias_prefix_of_longer_alias_does_not_match(db, tmp_path):
    identity.load_catalog(db, write_catalog(tmp_path, [{
        "tenant": "autocloud", "name": "payments-checkout", "environment": "prod",
        "region": "us-east1", "aliases": ["checkout-v2"]}]))
    resolved = identity.resolve(db, {"service": "checkout", "region": "us-east1"})
    # 'checkout' is only a prefix of the alias 'checkout-v2'; the quoted-token
    # match must refuse it and fall through to an inferred candidate.
    assert resolved["service_uid"] == "svc://inferred/checkout/prod/us-east1"
    assert resolved["status"] == "candidate"
    assert resolved["source"] == "inferred"


def test_alias_exact_token_resolves_to_confirmed_row(db, tmp_path):
    identity.load_catalog(db, write_catalog(tmp_path, [{
        "tenant": "autocloud", "name": "payments-checkout", "environment": "prod",
        "region": "us-east1", "aliases": ["checkout", "legacy-checkout"]}]))
    resolved = identity.resolve(db, {"service": "checkout", "region": "us-east1"})
    assert resolved["service_uid"] == "svc://autocloud/payments-checkout/prod/us-east1"
    assert resolved["status"] == "confirmed"


def test_catalog_match_is_region_scoped(db, tmp_path):
    identity.load_catalog(db, write_catalog(tmp_path, [{
        "tenant": "autocloud", "name": "checkout", "environment": "prod",
        "region": "us-east1"}]))
    resolved = identity.resolve(db, {"service": "checkout", "region": "eu-west1"})
    assert resolved["service_uid"] == "svc://inferred/checkout/prod/eu-west1"
    assert resolved["status"] == "candidate"


def test_unknown_service_lands_as_visible_inferred_candidate(db):
    resolved = identity.resolve(db, {"service": "ghost-svc", "region": "eu-west1"})
    assert resolved["service_uid"] == "svc://inferred/ghost-svc/prod/eu-west1"
    assert resolved["environment"] == "prod"
    assert resolved["source"] == "inferred"
    assert resolved["status"] == "candidate"
    # A second resolve reuses the candidate row rather than minting another.
    again = identity.resolve(db, {"service": "ghost-svc", "region": "eu-west1"})
    assert again["service_uid"] == resolved["service_uid"]
    with db.session() as s:
        assert len(s.execute(select(Service)).scalars().all()) == 1


# --- identity.load_catalog / Db.upsert_service ----------------------------


def test_load_catalog_reload_upserts_in_place_without_duplicates(db, tmp_path):
    count = identity.load_catalog(db, write_catalog(tmp_path, [{
        "tenant": "autocloud", "name": "checkout", "environment": "prod",
        "region": "us-east1", "runtime": "python312", "owner": "team-a"}]))
    assert count == 1
    identity.load_catalog(db, write_catalog(tmp_path, [{
        "tenant": "autocloud", "name": "checkout", "environment": "prod",
        "region": "us-east1", "runtime": "python312", "owner": "team-b"}],
        filename="services-v2.yaml"))
    with db.session() as s:
        rows = s.execute(select(Service)).scalars().all()
    assert len(rows) == 1
    assert rows[0].owner == "team-b"
    assert rows[0].runtime == "python312"
    assert rows[0].status == "confirmed"


def test_upsert_service_sparse_update_preserves_runtime_and_owner(db):
    uid = "svc://autocloud/checkout/prod/us-east1"
    db.upsert_service({
        "service_uid": uid, "name": "checkout", "environment": "prod",
        "region": "us-east1", "runtime": "python312",
        "architecture_version": "v3", "owner": "team-payments",
        "source": "catalog", "status": "confirmed"})
    # Sparse re-upsert: keys absent entirely, as a fixture loader would send.
    db.upsert_service({
        "service_uid": uid, "name": "checkout", "environment": "prod",
        "region": "us-east1"})
    with db.session() as s:
        row = s.get(Service, uid)
    assert row.runtime == "python312"
    assert row.owner == "team-payments"
    assert row.architecture_version == "v3"


# --- dossier state machine ------------------------------------------------


def test_propose_activate_supersede_lifecycle(store, db, clock):
    clock.set("2026-01-01T00:00:00Z")
    r1 = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized",
                       rationale="baseline from ep1")
    assert r1["status"] == "proposed"

    active1 = store.activate(r1["rev_id"], "alice")
    assert active1["status"] == "active"
    assert active1["owner_verified_by"] == "alice"
    assert active1["activated_at"] == "2026-01-01T00:00:00Z"

    # Activation is single-shot: the rev is no longer 'proposed'.
    assert "error" in store.activate(r1["rev_id"], "bob")

    # An unrelated field's active claim must survive supersession of this one.
    other = store.propose(SVC, "traffic_profile", {"peak": "daily"}, "asserted")
    store.activate(other["rev_id"], "alice")

    clock.set("2026-01-02T00:00:00Z")
    r2 = store.propose(SVC, "p99_baseline_ms", 220, "asserted")
    assert store.activate(r2["rev_id"], "bob")["status"] == "active"

    with db.session() as s:
        old = s.get(DossierRevision, r1["rev_id"])
    assert old.status == "superseded"
    assert old.superseded_by_rev == r2["rev_id"]
    assert old.deactivated_at == "2026-01-02T00:00:00Z"

    by_field = {c["field"]: c for c in store.get(SVC)["claims"]}
    assert by_field["p99_baseline_ms"]["value"] == 220
    assert by_field["p99_baseline_ms"]["rev_id"] == r2["rev_id"]
    assert by_field["traffic_profile"]["status"] == "active"


def test_agent_may_not_self_certify_governed_epistemic_types(store):
    for etype in ("approved", "observed", "inferred"):
        assert "error" in store.propose(SVC, "p99_baseline_ms", 1, etype)
    assert "error" in store.propose(SVC, "p99_baseline_ms", 1, "not-a-type")
    # The governed path (agent_originated=False) may carry them.
    ok = store.propose(SVC, "p99_baseline_ms", 1, "observed",
                       agent_originated=False)
    assert ok["status"] == "proposed"


def test_reject_transitions_only_proposed_revisions(store, db, clock):
    r = store.propose(SVC, "traffic_profile", "spiky", "hypothesized")
    rejected = store.reject(r["rev_id"], "carol")
    assert rejected["status"] == "rejected"
    assert rejected["owner_verified_by"] == "carol"

    a = store.propose(SVC, "traffic_profile", "flat", "hypothesized")
    store.activate(a["rev_id"], "alice")
    res = store.reject(a["rev_id"], "carol")
    # Reject off 'proposed' errors loudly; the active claim stays active
    # and keeps its original verifier.
    assert res == {"error": f"revision {a['rev_id']} is active, not proposed"}
    with db.session() as s:
        row = s.get(DossierRevision, a["rev_id"])
    assert row.status == "active"
    assert row.owner_verified_by == "alice"

    assert "error" in store.reject("rev_does_not_exist", "carol")


def test_activation_of_expired_proposal_marks_it_expired(store, db, clock):
    clock.set("2026-01-01T00:00:00Z")
    r = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized",
                      expires_at="2026-01-03T00:00:00Z")
    clock.set("2026-01-05T00:00:00Z")
    res = store.activate(r["rev_id"], "alice")
    assert "error" in res
    assert "expired" in res["error"]
    with db.session() as s:
        row = s.get(DossierRevision, r["rev_id"])
    assert row.status == "expired"
    assert row.deactivated_at == "2026-01-05T00:00:00Z"
    assert row.activated_at is None
    assert store.get(SVC)["claims"] == []


def test_sweep_expired_deactivates_only_overdue_active_claims(store, db, clock):
    clock.set("2026-01-01T00:00:00Z")
    doomed = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized",
                           expires_at="2026-01-04T00:00:00Z")
    store.activate(doomed["rev_id"], "alice")
    durable = store.propose(SVC, "traffic_profile", "flat", "hypothesized",
                            expires_at="2027-01-01T00:00:00Z")
    store.activate(durable["rev_id"], "alice")
    eternal = store.propose(SVC, "resource_envelope", {"cpu": 2}, "hypothesized")
    store.activate(eternal["rev_id"], "alice")

    clock.set("2026-01-10T00:00:00Z")
    assert store.sweep_expired() == 1
    with db.session() as s:
        row = s.get(DossierRevision, doomed["rev_id"])
    assert row.status == "expired"
    assert row.deactivated_at == "2026-01-10T00:00:00Z"
    assert {c["field"] for c in store.get(SVC)["claims"]} == {
        "traffic_profile", "resource_envelope"}
    # Nothing left to sweep.
    assert store.sweep_expired() == 0


def test_invalidate_architecture_expires_sensitive_fields_with_rationale(
        store, db, clock):
    clock.set("2026-01-01T00:00:00Z")
    sens1 = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized",
                          rationale="baseline from ep1")
    store.activate(sens1["rev_id"], "alice")
    sens2 = store.propose(SVC, "traffic_profile", "spiky", "asserted")
    store.activate(sens2["rev_id"], "alice")
    survivor = store.propose(SVC, "escalation_contact", "#payments-oncall",
                             "asserted")
    store.activate(survivor["rev_id"], "alice")
    foreign = store.propose(OTHER_SVC, "p99_baseline_ms", 90, "asserted")
    store.activate(foreign["rev_id"], "alice")

    clock.set("2026-02-01T00:00:00Z")
    assert store.invalidate_architecture(SVC, "v2") == 2

    with db.session() as s:
        s1 = s.get(DossierRevision, sens1["rev_id"])
        s2 = s.get(DossierRevision, sens2["rev_id"])
        keep = s.get(DossierRevision, survivor["rev_id"])
        other = s.get(DossierRevision, foreign["rev_id"])
    assert s1.status == "expired"
    assert s1.deactivated_at == "2026-02-01T00:00:00Z"
    assert s1.rationale == "baseline from ep1 [expired: architecture change to v2]"
    assert s2.status == "expired"
    assert s2.rationale.endswith("[expired: architecture change to v2]")
    # Non-sensitive field survives; other services are untouched.
    assert keep.status == "active"
    assert "[expired" not in (keep.rationale or "")
    assert other.status == "active"


def test_governed_value_returns_only_approved_or_observed_active_claims(
        store, clock):
    # An asserted active claim informs; it must never govern behavior.
    asserted = store.propose(SVC, "stabilization_window_minutes", 5, "asserted")
    store.activate(asserted["rev_id"], "alice")
    assert store.governed_value(SVC, "stabilization_window_minutes") is None

    # Human promotion upgrades the epistemic type at activation -> governs.
    promoted = store.propose(SVC, "stabilization_window_minutes", 45,
                             "hypothesized")
    store.activate(promoted["rev_id"], "alice", epistemic_type="approved")
    assert store.governed_value(SVC, "stabilization_window_minutes") == 45

    # Observed (via the governed proposal path) also governs.
    obs = store.propose(SVC, "error_rate_baseline", 0.002, "observed",
                        agent_originated=False)
    store.activate(obs["rev_id"], "collector")
    assert store.governed_value(SVC, "error_rate_baseline") == 0.002

    # A merely proposed approved claim does not govern until activated.
    store.propose(SVC, "p99_baseline_ms", 200, "approved",
                  agent_originated=False)
    assert store.governed_value(SVC, "p99_baseline_ms") is None


def test_as_of_read_hides_claim_outside_its_activation_window(store, clock):
    clock.set("2026-01-01T00:00:00Z")
    r1 = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized")
    store.activate(r1["rev_id"], "alice")

    clock.set("2026-01-03T00:00:00Z")
    r2 = store.propose(SVC, "p99_baseline_ms", 240, "asserted")
    store.activate(r2["rev_id"], "bob")
    # r1's record-time window is [2026-01-01, 2026-01-03).

    def visible_at(as_of):
        return [(c["rev_id"], c["value"])
                for c in store.get(SVC, as_of=as_of)["claims"]]

    assert visible_at("2025-12-31T00:00:00Z") == []
    assert visible_at("2026-01-02T00:00:00Z") == [(r1["rev_id"], 180)]
    # Half-open boundary: at the deactivation instant the successor rules.
    assert visible_at("2026-01-03T00:00:00Z") == [(r2["rev_id"], 240)]
    assert visible_at("2026-01-04T00:00:00Z") == [(r2["rev_id"], 240)]


def test_offset_form_as_of_is_normalized_to_utc_before_comparison(store, clock):
    clock.set("2026-01-01T06:00:00Z")
    r = store.propose(SVC, "p99_baseline_ms", 180, "hypothesized")
    store.activate(r["rev_id"], "alice")

    # 10:00+05:30 is 04:30Z — BEFORE activation (06:00Z). Compared
    # lexicographically unnormalized it sorts after "...T06:00:00Z" and
    # would leak the claim into the past.
    assert store.get(SVC, as_of="2026-01-01T10:00:00+05:30")["claims"] == []
    # 12:00+05:30 is 06:30Z — after activation: visible.
    assert [c["rev_id"] for c in
            store.get(SVC, as_of="2026-01-01T12:00:00+05:30")["claims"]
            ] == [r["rev_id"]]
