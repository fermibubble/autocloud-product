"""End-to-end loop integration WITHOUT live processes: gcp_sim's world +
gcp-observe's collectors + rollout-intel's episode/checkpoint/policy chain,
wired in-process. Proves the whole Phase-1 spine before any MCP wiring:
deploy -> episode -> per-stage bundles -> policy -> verdict recording,
including the policy_conflict rejection and the insufficient-evidence path.
"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "intel"))
sys.path.insert(0, str(ROOT / "mcp-servers" / "gcp"))
sys.path.insert(0, str(ROOT / "sim"))

import envelope as minting  # noqa: E402
import gcp_sim  # noqa: E402
from rollout_intel.db import STAGE_LADDER  # noqa: E402
from rollout_intel.policy import PolicyPack, evaluate  # noqa: E402
from rollout_intel.service import Intel  # noqa: E402


@pytest.fixture()
def world():
    return gcp_sim.World(seed=42)


@pytest.fixture()
def intel(tmp_path):
    return Intel(str(tmp_path / "intel.db"),
                 str(ROOT / "policies" / "rollout-slo.yaml"),
                 str(ROOT / "catalog" / "services.yaml"))


def bundle_from_world(world: gcp_sim.World, service: str, stage: str) -> list[dict]:
    """Mirror gcp-observe's stage_bundle against the in-process world —
    same envelope minting path (shared signing module)."""
    envs = [minting.mint("workload_state", {},
                         {"services": [{"name": s["name"],
                                        "latestReadyRevision": s["revision"]}
                                       for s in world.services.values()]})]
    if stage in ("T+5", "T+15", "T+30"):
        envs.append(minting.mint(
            "metric_window", {"service": service},
            {"metric_type": "run.googleapis.com/request_count",
             "series": [{"metric": "count",
                         "points": [{"end": "x", "value": world.request_count(service, 10)}]}]},
            {"sample_count": world.request_count(service, 10)}))
        envs.append(minting.mint(
            "metric_window", {"service": service},
            {"metric_type": "run.googleapis.com/request_latencies",
             "series": [{"metric": "lat", "points": [{"end": "x", "value": world.p99_ms(service)}]}]},
            {"sample_count": world.request_count(service, 10)}))
        envs.append(minting.mint(
            "metric_window", {"service": service},
            {"metric_type": "run.googleapis.com/http_5xx_rate",
             "series": [{"metric": "err", "points": [{"end": "x", "value": world.err_rate(service)}]}]},
            {"sample_count": world.request_count(service, 10)}))
    if stage in ("T+15", "T+30"):
        envs.append(minting.mint(
            "log_scan", {"service": service},
            {"query": "severity>=ERROR", "entries": world.log_entries(service, 20)},
            {"entry_count": len(world.log_entries(service, 20))}))
    if stage == "T+30":
        # Policy v2: the decision stage needs temporal fast-forward
        # evidence — mirror the FF result-envelope pull run_stage_checks
        # does when FF_API is set (benign outcome for these fixtures).
        envs.append(minting.mint(
            "fastforward_result",
            {"service": service, "episode_id": "ep-test", "stage": "T+30"},
            {"outcome": "no_material_temporal_hazard", "request_id": "ffr-test",
             "episode_id": "ep-test", "service": service, "hazards": [],
             "fidelity": {"axes": {}, "aggregate": 1.0, "gates_met": True,
                          "unsupported": []},
             "budget": {"granted": {}, "spent": {}}, "plan_digest": "",
             "counterexample_ids": []},
            source="rollout-fastforward", ttl_seconds=86400))
    return envs


EXPECTED = {
    "demo-healthy": {"policy": "pass", "verdict": "healthy"},
    "demo-latency": {"policy": "fail", "verdict": "regression-suspected"},
    "demo-errors": {"policy": "fail", "verdict": "regression-suspected"},
    "demo-thin": {"policy": "insufficient_evidence", "verdict": "insufficient-evidence"},
}


def drive_episode(world, intel, service: str) -> dict:
    event = world.deploy(service)
    episode = intel.create_episode(event)
    episode_id = episode["episode_id"]
    for stage in STAGE_LADDER:
        intel.open_checkpoint(episode_id, stage, f"ses-test-{service}-{stage}")
        envs = bundle_from_world(world, service, stage)
        policy = evaluate(intel.pack, stage, envs)
        verdict = ("healthy" if policy["policy_status"] == "pass"
                   else "insufficient-evidence"
                   if policy["policy_status"] == "insufficient_evidence"
                   else "regression-suspected")
        out = intel.record(episode_id, stage, envs, verdict,
                           f"scripted test at {stage}", f"# report {stage}", [], [])
        assert "error" not in out, out
    return intel.db.one("SELECT * FROM episodes WHERE episode_id=?", (episode_id,))


@pytest.mark.parametrize("service", list(EXPECTED))
def test_full_ladder_per_fixture_service(world, intel, service):
    episode = drive_episode(world, intel, service)
    assert episode["status"] == "awaiting_outcome"
    assert episode["final_verdict"] == EXPECTED[service]["verdict"]
    cps = intel.db.query("SELECT * FROM checkpoints WHERE episode_id=? ORDER BY report_version",
                         (episode["episode_id"],))
    assert [c["report_version"] for c in cps] == [1, 2, 3, 4]
    final = cps[-1]
    assert final["policy_status"] == EXPECTED[service]["policy"]
    obs = intel.db.query("SELECT sig_verified FROM observations WHERE episode_id=?",
                         (episode["episode_id"],))
    assert obs and all(o["sig_verified"] == 1 for o in obs)


def test_policy_conflict_rejects_healthy_lie(world, intel):
    event = world.deploy("demo-latency")
    episode = intel.create_episode(event)
    intel.open_checkpoint(episode["episode_id"], "T+0", "ses-x")
    envs = bundle_from_world(world, "demo-latency", "T+0")
    ok = intel.record(episode["episode_id"], "T+0", envs, "healthy", "fine", "# r", [], [])
    assert "error" not in ok  # T+0 genuinely passes

    intel.open_checkpoint(episode["episode_id"], "T+5", "ses-y")
    envs5 = bundle_from_world(world, "demo-latency", "T+5")
    lie = intel.record(episode["episode_id"], "T+5", envs5, "healthy",
                       "looks fine to me", "# r", [], [])
    assert "policy_conflict" in lie.get("error", "")
    # And the honest verdict then records cleanly.
    honest = intel.record(episode["episode_id"], "T+5", envs5, "regression-suspected",
                          "p99 breached the envelope", "# r", [], [])
    assert "error" not in honest


def test_service_name_resolution_for_scripted_reviewers(world, intel):
    event = world.deploy("demo-healthy")
    episode = intel.create_episode(event)
    intel.open_checkpoint(episode["episode_id"], "T+0", "ses-z")
    assert intel.resolve_episode("demo-healthy", "T+0") == episode["episode_id"]
    # ambiguity (two open same-stage checkpoints for one service) errors
    event2 = world.deploy("demo-healthy")
    ep2 = intel.create_episode(event2)
    intel.open_checkpoint(ep2["episode_id"], "T+0", "ses-w")
    assert intel.resolve_episode("demo-healthy", "T+0") is None


def test_decision_quality_metrics(world, intel):
    episode = drive_episode(world, intel, "demo-latency")
    # Label it via the outcome path: it really did regress.
    intel.db.execute(
        "UPDATE episodes SET final_label='regressed', labeled_at='x', status='closed' "
        "WHERE episode_id=?", (episode["episode_id"],))
    metrics = intel.decision_quality()
    assert metrics["labeledEpisodes"] == 1
    assert metrics["falseSafe"] == 0  # verdict was regression-suspected: correct

    importlib.invalidate_caches()


def test_architecture_change_via_deploy_event_expires_sensitive_claims(world, intel):
    """Review finding: the old comparison read the architecture from the
    same service row it compared against, so invalidation never fired.
    The deploy EVENT is the authority; a v2 deploy must expire
    architecture-sensitive dossier claims and teach the row v2."""
    uid = "svc://autocloud/demo-healthy/prod/us-central1"
    rev = intel.dossiers.propose(uid, "p99_baseline_ms", 185, "asserted",
                                 agent_originated=False)
    intel.dossiers.activate(rev["rev_id"], "op")
    rev2 = intel.dossiers.propose(uid, "owner_notes", "team-a", "asserted",
                                  agent_originated=False)
    intel.dossiers.activate(rev2["rev_id"], "op")

    event = world.deploy("demo-healthy", architecture_version="v2")
    episode = intel.create_episode(event)

    claims = intel.dossiers.get(uid)["claims"]
    assert [c["field"] for c in claims] == ["owner_notes"]  # sensitive claim gone
    svc = intel.db.one("SELECT architecture_version FROM services WHERE service_uid=?", (uid,))
    assert svc["architecture_version"] == "v2"
    assert episode["architecture_version"] == "v2"


def test_governed_window_never_skips_t30_temporal_rule(world, intel):
    """Dynamic scheduling under policy v2: even an OBSERVED stabilization
    window of 15 minutes must not end the ladder at T+15 — the T+30-only
    temporal-evidence rule raises the full-coverage floor to 30, so the
    ladder runs to its natural end. An ASSERTED window changes nothing."""
    uid = "svc://autocloud/demo-healthy/prod/us-central1"
    rev = intel.dossiers.propose(uid, "stabilization_window_minutes", 15, "asserted",
                                 agent_originated=False)
    intel.dossiers.activate(rev["rev_id"], "op", epistemic_type="observed")

    event = world.deploy("demo-healthy")
    episode = intel.create_episode(event)
    for stage in ("T+0", "T+5", "T+15"):
        intel.open_checkpoint(episode["episode_id"], stage, f"ses_{stage}")
        envs = bundle_from_world(world, "demo-healthy", stage)
        result = intel.record(episode["episode_id"], stage, envs, "healthy",
                              "ok", "# r", [], [])
        assert "error" not in result, result
    # The governed window (15) is outranked by the coverage floor (30).
    assert result["next_check_at"] == "+15m"
    intel.open_checkpoint(episode["episode_id"], "T+30", "ses_T+30")
    envs = bundle_from_world(world, "demo-healthy", "T+30")
    result = intel.record(episode["episode_id"], "T+30", envs, "healthy",
                          "ok", "# r", [], [])
    assert "error" not in result, result
    assert result["next_check_at"] is None
    row = intel.db.one("SELECT status, final_verdict FROM episodes WHERE episode_id=?",
                       (episode["episode_id"],))
    assert row["status"] == "awaiting_outcome" and row["final_verdict"] == "healthy"

    # An asserted (ungoverned) window on demo-thin changes nothing: T+15
    # still schedules a next check.
    uid_thin = "svc://autocloud/demo-thin/prod/us-central1"
    rev = intel.dossiers.propose(uid_thin, "stabilization_window_minutes", 15, "asserted",
                                 agent_originated=False)
    intel.dossiers.activate(rev["rev_id"], "op")  # stays asserted
    event = world.deploy("demo-thin")
    episode = intel.create_episode(event)
    intel.open_checkpoint(episode["episode_id"], "T+15", "ses_t15")
    intel.run_stage_checks(episode["episode_id"], "T+15")
    result = intel.record(episode["episode_id"], "T+15", [], "insufficient-evidence",
                          "thin", "# r", [], [])
    assert result["next_check_at"] == "+15m"


def test_signed_evidence_from_another_service_is_rejected(world, intel):
    """Review finding F1: a validly SIGNED envelope for a different
    service must not satisfy this episode's policy — signature proves
    provenance, scope proves relevance."""
    event = world.deploy("demo-errors")
    episode = intel.create_episode(event)
    intel.open_checkpoint(episode["episode_id"], "T+5", "ses_x")
    healthy_envs = bundle_from_world(world, "demo-healthy", "T+5")
    result = intel.record(episode["episode_id"], "T+5", healthy_envs,
                          "healthy", "borrowed evidence", "# r", [], [])
    assert "error" in result and "scope_mismatch" in result["error"]


def test_double_complete_is_a_loud_conflict(world, intel):
    """Review finding F2: the losing racer of a double record must not
    report success or touch the episode."""
    event = world.deploy("demo-healthy")
    episode = intel.create_episode(event)
    cp = intel.open_checkpoint(episode["episode_id"], "T+0", "ses_1")
    first = intel.db.complete_checkpoint(cp["checkpoint_id"], "healthy", "pass",
                                         "v1", False, "# r", "+5m")
    assert first is not None and first["report_version"] == 1
    second = intel.db.complete_checkpoint(cp["checkpoint_id"], "regression-suspected",
                                          "fail", "v1", False, "# r2", None)
    assert second is None
    row = intel.db.one("SELECT stage_verdict, status FROM checkpoints c "
                       "JOIN episodes e ON e.episode_id=c.episode_id "
                       "WHERE c.checkpoint_id=?", (cp["checkpoint_id"],))
    assert row["stage_verdict"] == "healthy"  # the winner's verdict stands


def test_open_checkpoint_rearm_is_idempotent_while_open(world, intel):
    """Review finding F9: a relay resume re-arms the same open checkpoint
    with its new session instead of tripping UNIQUE(episode_id, stage)."""
    event = world.deploy("demo-healthy")
    episode = intel.create_episode(event)
    cp1 = intel.open_checkpoint(episode["episode_id"], "T+0", "ses_dead")
    cp2 = intel.open_checkpoint(episode["episode_id"], "T+0", "ses_alive")
    assert cp1["checkpoint_id"] == cp2["checkpoint_id"]
    assert cp2["session_id"] == "ses_alive"
