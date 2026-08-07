"""Orchestration-layer invariants of Intel.record and its neighbors:
scope_mismatch, governed stabilization windows (and their full-coverage
floor), resolve_episode discrimination, outcome label-once, checkpoint
reopen-after-complete, and retrieval scope widening.

All tests run against a real tmp-path SQLite Db (via Intel or Db directly).
Envelopes are minted with the REAL signing side (servers/gcp-observe/
envelope.py, loaded by path as in test_policy_and_envelope.py). The outcome
label-once test exercises the actual REST branch: build_rest() is bound to
an ephemeral loopback port and driven with httpx, in-process.
"""

import importlib.util
import threading
from pathlib import Path

import httpx
import pytest
import yaml
from sqlalchemy import select, update

from rollout_intel.db import Db
from rollout_intel.envelope import verify
from rollout_intel.models import Checkpoint, Episode, Outcome
from rollout_intel.retrieval import find_precedents
from rollout_intel.service import Intel, build_rest

# --- load the minting side (gcp-observe) by path -----------------------------

_MINT_PATH = Path(__file__).resolve().parents[2] / "gcp-observe" / "envelope.py"
_spec = importlib.util.spec_from_file_location("gcp_observe_envelope_guards", _MINT_PATH)
_mint_side = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mint_side)
mint = _mint_side.mint


# --- fixtures / helpers ------------------------------------------------------

CATALOG = {"services": [
    {"tenant": "autocloud", "name": "checkout", "environment": "prod",
     "region": "us-east1", "runtime": "cloud-run",
     "architecture_version": "v1", "owner": "team-payments"},
    {"tenant": "autocloud", "name": "search", "environment": "prod",
     "region": "us-east1", "runtime": "cloud-run",
     "architecture_version": "v1", "owner": "team-search"},
]}

CHECKOUT_UID = "svc://autocloud/checkout/prod/us-east1"

LADDER = [
    {"stage": "G+0", "offset_minutes": 0},
    {"stage": "G+10", "offset_minutes": 10},
    {"stage": "G+30", "offset_minutes": 30},
    {"stage": "G+60", "offset_minutes": 60},
]

# Single rule at the FIRST stage: full-coverage floor is 0, so governed
# windows act on their own value. No exit block: exit criteria stay out
# of the way of the window tests.
GUARD_POLICY = {
    "name": "guard-pack", "version": 1,
    "rules": [{"id": "wl", "type": "workload_serving", "stages": ["G+0"]}],
    "checkpoints": {
        "ladder": LADDER,
        "bounds": {"min_interval_minutes": 2, "max_interval_minutes": 60},
    },
}

# Single rule bound to a LATE stage only: the full-coverage floor is that
# stage's offset (30), so a smaller governed window must wait for it.
LATE_RULE_POLICY = {
    "name": "late-pack", "version": 1,
    "rules": [{"id": "late-fatal", "type": "no_new_fatal", "stages": ["G+30"]}],
    "checkpoints": {
        "ladder": LADDER,
        "bounds": {"min_interval_minutes": 2, "max_interval_minutes": 60},
    },
}


@pytest.fixture
def make_intel(tmp_path, monkeypatch):
    # No projector: dossier writes must not attempt network projection.
    monkeypatch.delenv("ENSEMBLE_TOKEN", raising=False)

    def _make(policy_doc):
        policy = tmp_path / "policy.yaml"
        policy.write_text(yaml.safe_dump(policy_doc), encoding="utf-8")
        catalog = tmp_path / "services.yaml"
        catalog.write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
        return Intel(str(tmp_path / "intel.db"), str(policy), str(catalog))

    return _make


def deploy_event(service="checkout", n=1):
    return {"type": "deployment_completed", "service": service,
            "region": "us-east1", "from_revision": f"r{n}",
            "to_revision": f"r{n + 1}", "image_digest": f"sha256:{n:03d}",
            "strategy": "canary", "change_classes": ["code"]}


def record(intel, episode_or_service, stage, verdict="insufficient-evidence",
           envs=None):
    return intel.record(episode_or_service, stage, envs or [], verdict,
                        "reasoning", "# report", [], [])


def wl_env(service):
    """A validly signed workload_state envelope scoped to `service`."""
    return mint("workload_state", {"service": service, "region": "us-east1"},
                {"services": [{"name": service, "revision": "r2"}]})


def episode_row(intel, episode_id):
    with intel.db.session() as s:
        return s.get(Episode, episode_id)


def approve_window(intel, minutes, epistemic_type="approved"):
    """Propose + human-promote a governed stabilization window claim."""
    if epistemic_type == "observed":
        rev = intel.dossiers.propose(
            CHECKOUT_UID, "stabilization_window_minutes", minutes, "observed",
            agent_originated=False)
        activated = intel.dossiers.activate(rev["rev_id"], "collector")
    else:
        rev = intel.dossiers.propose(
            CHECKOUT_UID, "stabilization_window_minutes", minutes, "hypothesized")
        activated = intel.dossiers.activate(rev["rev_id"], "alice",
                                            epistemic_type=epistemic_type)
    assert activated["status"] == "active"
    return activated


# --- 1. scope_mismatch guard -------------------------------------------------


def test_scope_mismatch_rejects_foreign_evidence_and_keeps_checkpoint_open(make_intel):
    intel = make_intel(GUARD_POLICY)
    ep = intel.create_episode(deploy_event("checkout"))["episode_id"]
    intel.open_checkpoint(ep, "G+0", "sess-1")

    foreign = wl_env("search")  # validly signed — for the WRONG service
    ok, reason = verify(foreign)
    assert ok and reason == "ok"

    r = record(intel, ep, "G+0", verdict="healthy", envs=[foreign])
    assert r["error"].startswith("scope_mismatch:")
    assert foreign["observation_id"] in r["error"]
    assert "checkout" in r["error"]

    # The checkpoint survives the rejection, still open...
    cp = intel.open_checkpoint_for(ep, "G+0")
    assert cp is not None
    assert cp["completed_at"] is None
    # ...and correctly scoped evidence still records against it.
    good = record(intel, ep, "G+0", verdict="healthy", envs=[wl_env("checkout")])
    assert good["policy_status"] == "pass"
    assert good["checkpoint_id"] == cp["checkpoint_id"]


# --- 2. governed stabilization window ---------------------------------------


@pytest.mark.parametrize("epistemic_type", ["approved", "observed"])
def test_governed_window_ends_ladder_at_or_past_its_offset(make_intel, epistemic_type):
    intel = make_intel(GUARD_POLICY)
    approve_window(intel, 10, epistemic_type=epistemic_type)
    ep = intel.create_episode(deploy_event("checkout"))["episode_id"]

    # G+10's offset (10) >= window (10) and >= the floor (0): the ladder
    # ends here even though G+30/G+60 remain in the policy's chain.
    intel.open_checkpoint(ep, "G+10", "sess-1")
    r = record(intel, ep, "G+10")
    assert r["next_check_at"] is None
    assert r["next_check"]["ladder_end"] == "governed_window"
    assert episode_row(intel, ep).status == "awaiting_outcome"


def test_hypothesized_window_never_ends_ladder(make_intel):
    intel = make_intel(GUARD_POLICY)
    # Active but merely hypothesized: governed_value refuses it, so the
    # ladder chain proceeds as if no window existed.
    rev = intel.dossiers.propose(
        CHECKOUT_UID, "stabilization_window_minutes", 10, "hypothesized")
    assert intel.dossiers.activate(rev["rev_id"], "alice")["status"] == "active"
    assert intel.dossiers.governed_value(
        CHECKOUT_UID, "stabilization_window_minutes") is None

    ep = intel.create_episode(deploy_event("checkout"))["episode_id"]
    intel.open_checkpoint(ep, "G+10", "sess-1")
    r = record(intel, ep, "G+10")
    assert r["next_check_at"] == "+20m"  # G+10 -> G+30
    assert "ladder_end" not in r["next_check"]
    assert episode_row(intel, ep).status == "in_progress"


# --- 3. _min_full_coverage_offset floor --------------------------------------


def test_full_coverage_floor_defers_governed_window_until_late_rule_stage(make_intel):
    intel = make_intel(LATE_RULE_POLICY)
    assert intel._min_full_coverage_offset() == 30.0
    approve_window(intel, 5)  # smaller than the late rule's stage offset
    ep = intel.create_episode(deploy_event("checkout"))["episode_id"]

    # G+10 (offset 10) is past the window (5) but before the floor (30):
    # the ladder must NOT end — the T+30-style rule has not had its stage.
    intel.open_checkpoint(ep, "G+10", "sess-1")
    r = record(intel, ep, "G+10")
    assert r["next_check_at"] == "+20m"
    assert "ladder_end" not in r["next_check"]

    # At G+30 the floor is reached; the window ends the ladder before G+60.
    intel.open_checkpoint(ep, "G+30", "sess-2")
    r = record(intel, ep, "G+30")
    assert r["next_check_at"] is None
    assert r["next_check"]["ladder_end"] == "governed_window"


# --- 4. resolve_episode discrimination ---------------------------------------


def test_multiple_live_episodes_error_verbatim_and_explicit_id_bypasses(make_intel):
    intel = make_intel(GUARD_POLICY)
    ep1 = intel.create_episode(deploy_event("checkout", 1))["episode_id"]
    ep2 = intel.create_episode(deploy_event("checkout", 2))["episode_id"]
    intel.open_checkpoint(ep1, "G+0", "sess-1")
    intel.open_checkpoint(ep2, "G+0", "sess-2")

    r = record(intel, "checkout", "G+0")
    assert r["error"] == ("multiple live episodes for checkout at G+0; "
                          "pass an episode id")
    # Ambiguity blocked nothing for an explicit id: it records normally.
    ok = record(intel, ep1, "G+0")
    assert ok["checkpoint_id"]
    assert ok["policy_status"] == "insufficient_evidence"


def test_no_open_checkpoint_resolvable_message(make_intel):
    intel = make_intel(GUARD_POLICY)
    # 'search' exists in the catalog but has no episodes/checkpoints at all.
    r = record(intel, "search", "G+0")
    assert r["error"] == "no open G+0 checkpoint resolvable from 'search'"


def test_explicit_ep_and_fx_ids_pass_through_resolution(make_intel):
    intel = make_intel(GUARD_POLICY)
    # resolve_episode never second-guesses an explicit id, even an unknown one.
    assert intel.resolve_episode("ep_missing", "G+0") == ("ep_missing", None)
    assert intel.resolve_episode("fx_missing", "G+0") == ("fx_missing", None)
    # record() then fails at the checkpoint lookup, not at resolution.
    r = record(intel, "ep_missing", "G+0")
    assert r["error"].startswith("no open checkpoint for episode ep_missing")


# --- 5. outcome label-once ---------------------------------------------------


def test_outcome_label_applies_once_via_rest(make_intel):
    intel = make_intel(GUARD_POLICY)
    ep = intel.create_episode(deploy_event("checkout"))["episode_id"]
    intel.open_checkpoint(ep, "G+60", "sess-1")
    r = record(intel, ep, "G+60")  # final stage: ladder closed
    assert r["next_check"]["ladder_end"] == "final_stage"
    assert episode_row(intel, ep).status == "awaiting_outcome"

    server = build_rest(intel, 0)  # ephemeral loopback port
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{port}/intel/episodes/{ep}/outcome"
        first = httpx.post(url, json={"horizon": "24h", "source": "collector",
                                      "final_label": "healthy"}, timeout=10)
        assert first.json() == {"recorded": True, "label_applied": True}
        # Second label — even a human's — is recorded as an outcome but the
        # episode's label is first-wins: never overwritten.
        second = httpx.post(url, json={"horizon": "final", "source": "human",
                                       "final_label": "regressed"}, timeout=10)
        assert second.json() == {"recorded": True, "label_applied": False}
    finally:
        server.shutdown()
        server.server_close()

    row = episode_row(intel, ep)
    assert row.final_label == "healthy"
    assert row.status == "closed"
    assert row.final_verdict == "insufficient-evidence"  # untouched by outcomes
    with intel.db.session() as s:
        horizons = s.execute(
            select(Outcome.horizon).where(Outcome.episode_id == ep)
        ).scalars().all()
    assert sorted(horizons) == ["24h", "final"]  # both outcomes kept


def test_completion_after_label_does_not_reopen_closed_episode(tmp_path):
    db = Db(str(tmp_path / "episodes.db"))
    db.upsert_service({
        "service_uid": "svc-a", "name": "svc-a", "environment": "prod",
        "region": "us-east1", "runtime": "cloud-run",
        "architecture_version": "v1"})
    ep = db.create_episode("svc-a", {"architecture_version": "v1"}, {})
    cp = db.open_checkpoint(ep["episode_id"], "T+30", "sess-1",
                            "2026-01-01T01:00:00Z")
    # An outcome labels (and closes) the episode while the final checkpoint
    # is still open — the collector's race, in miniature.
    with db.session() as s:
        s.execute(update(Episode)
                  .where(Episode.episode_id == ep["episode_id"])
                  .values(final_label="rolled_back",
                          labeled_at="2026-01-01T02:00:00Z", status="closed"))
    done = db.complete_checkpoint(cp["checkpoint_id"], "healthy", "pass",
                                  "pol-1", False, "# late", None)
    # The checkpoint itself completes...
    assert done is not None
    assert done["stage_verdict"] == "healthy"
    # ...but the final_label.is_(None) guard leaves the episode closed and
    # never stamps the late verdict over the labeled record.
    with db.session() as s:
        row = s.get(Episode, ep["episode_id"])
    assert row.status == "closed"
    assert row.final_label == "rolled_back"
    assert row.final_verdict is None


# --- 6. open_checkpoint reopen-after-complete --------------------------------


def test_open_after_complete_returns_completed_row_unrearmed(tmp_path):
    db = Db(str(tmp_path / "episodes.db"))
    db.upsert_service({
        "service_uid": "svc-a", "name": "svc-a", "environment": "prod",
        "region": "us-east1"})
    ep = db.create_episode("svc-a", {"architecture_version": "v1"}, {})
    cp = db.open_checkpoint(ep["episode_id"], "T+0", "sess-1",
                            "2026-01-01T01:00:00Z")
    db.complete_checkpoint(cp["checkpoint_id"], "healthy", "pass", "pol-1",
                           False, "# report", "2026-01-01T02:00:00Z")

    # Re-open of a completed (episode, stage): no exception, no loop — the
    # COMPLETED row comes back as-is, session/schedule NOT re-armed.
    again = db.open_checkpoint(ep["episode_id"], "T+0", "sess-2",
                               "2026-01-01T03:00:00Z")
    assert again["checkpoint_id"] == cp["checkpoint_id"]
    assert again["completed_at"] is not None
    assert again["stage_verdict"] == "healthy"
    assert again["session_id"] == "sess-1"
    assert again["scheduled_at"] == "2026-01-01T01:00:00Z"
    with db.session() as s:
        rows = s.execute(select(Checkpoint)
                         .where(Checkpoint.episode_id == ep["episode_id"])
                         ).scalars().all()
    assert len(rows) == 1


def test_duplicate_open_of_still_open_checkpoint_rearms_new_session(tmp_path):
    db = Db(str(tmp_path / "episodes.db"))
    db.upsert_service({
        "service_uid": "svc-a", "name": "svc-a", "environment": "prod",
        "region": "us-east1"})
    ep = db.create_episode("svc-a", {"architecture_version": "v1"}, {})
    first = db.open_checkpoint(ep["episode_id"], "T+0", "sess-1",
                               "2026-01-01T01:00:00Z")
    second = db.open_checkpoint(ep["episode_id"], "T+0", "sess-2",
                                "2026-01-01T01:05:00Z")
    assert second["checkpoint_id"] == first["checkpoint_id"]
    assert second["session_id"] == "sess-2"
    assert second["scheduled_at"] == "2026-01-01T01:05:00Z"
    assert second["completed_at"] is None


# --- 7. retrieval widening rungs ---------------------------------------------

SVC_A = {"service_uid": "svc-checkout-a", "name": "checkout-a",
         "environment": "prod", "region": "us-east1", "runtime": "cloud-run",
         "architecture_version": "v1", "owner": "team-a"}
SVC_B = {"service_uid": "svc-checkout-b", "name": "checkout-b",
         "environment": "prod", "region": "us-east1", "runtime": "cloud-run",
         "architecture_version": "v1", "owner": "team-b"}


def _fp(arch="v1"):
    return {"fingerprint_version": "v1", "service_family": "checkout",
            "runtime": "cloud-run", "environment": "prod",
            "architecture_version": arch, "strategy": "canary",
            "change_classes": ["code"], "image_digest": "sha256:abc"}


def _labeled(db, service_uid, fp, label):
    ep = db.create_episode(service_uid, fp,
                           {"from_revision": "r1", "to_revision": "r2"})
    with db.session() as s:
        s.execute(update(Episode)
                  .where(Episode.episode_id == ep["episode_id"])
                  .values(final_label=label, labeled_at="2026-01-01T00:00:00Z",
                          status="closed", final_verdict="healthy",
                          architecture_version=fp["architecture_version"]))
    return ep["episode_id"]


def _returned_ids(result):
    return {p["episode_id"] for p in result["healthy"] + result["unhealthy"]}


def test_family_rung_widens_when_service_rung_is_empty(tmp_path):
    db = Db(str(tmp_path / "episodes.db"))
    db.upsert_service(dict(SVC_A))
    db.upsert_service(dict(SVC_B))
    # All history belongs to the family-mate service B; A itself has none.
    fam = {_labeled(db, SVC_B["service_uid"], _fp(), "healthy") for _ in range(2)}
    fam |= {_labeled(db, SVC_B["service_uid"], _fp(), "regressed"),
            _labeled(db, SVC_B["service_uid"], _fp(), "rolled_back")}

    result = find_precedents(db, SVC_A, _fp())
    assert result["scope_rung"] == "family"
    assert _returned_ids(result) == fam
    assert result["insufficient_precedent"] is False


def test_architecture_hard_filter_excludes_family_mates(tmp_path):
    db = Db(str(tmp_path / "episodes.db"))
    db.upsert_service(dict(SVC_A))
    db.upsert_service(dict(SVC_B))
    for _ in range(2):
        _labeled(db, SVC_B["service_uid"], _fp(), "healthy")
    v1_unhealthy = _labeled(db, SVC_B["service_uid"], _fp(), "regressed")
    # Same family, WRONG architecture: history, not precedent — its
    # exclusion is what leaves the unhealthy side short.
    v2_unhealthy = _labeled(db, SVC_B["service_uid"], _fp(arch="v2"),
                            "rolled_back")

    result = find_precedents(db, SVC_A, _fp(arch="v1"))
    assert v2_unhealthy not in _returned_ids(result)
    assert v1_unhealthy in _returned_ids(result)
    # The arch filter applies on EVERY rung: widening all the way to the
    # runtime rung never readmits it, so the set stays one-sided.
    assert result["scope_rung"] == "runtime"
    assert result["insufficient_precedent"] is True
