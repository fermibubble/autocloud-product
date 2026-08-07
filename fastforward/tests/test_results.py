"""Results tests: the outcome precedence table, the fidelity gate on a
clean bill, one-shot snapshots, terminal-only envelope release, the dead-
probe-target degrade path (never a pass), and fixture loading."""

import json
from pathlib import Path

import pytest

from rollout_fastforward import envelope, results, service
from rollout_fastforward.db import Db

LEAK_EVENT = {
    "to_revision": "r2", "from_revision": "r1",
    "change_manifest": {"items": [
        {"kind": "dependency", "name": "pg-pool", "from": "2.1.0", "to": "3.0.0"}]},
}

GOOD_FID = {"axes": {}, "aggregate": 0.7, "gates_met": True, "unsupported": []}
BAD_FID = {"axes": {}, "aggregate": 0.2, "gates_met": False, "unsupported": ["concurrency"]}


def d(disposition, hid="hz_1", klass="resource_lifecycle", mode="probe"):
    return {"hazard_id": hid, "class": klass, "disposition": disposition,
            "mode": mode}


def mk_request(db, episode="ep_t1", svc="demo-leak", state="ANALYZING"):
    row = db.create_request(episode, svc, {"items": []}, 240,
                            {"max_probe_seconds": 120, "max_steps": 4})
    for s in ("COMPILED", "PLANNED", "RUNNING", "ANALYZING"):
        if state == "RECEIVED":
            break
        row = db.set_state(row["request_id"], s)
        if s == state:
            break
    return row


SPENT = {"probe_seconds": 1.0, "steps": 1}


@pytest.mark.parametrize("dispositions,fids,outcome,state", [
    ([d("counterexample"), d("within_envelope", "hz_2")], [GOOD_FID],
     "temporal_counterexample", "COUNTEREXAMPLE"),
    ([d("counterexample"), d("inconclusive_budget", "hz_2"), d("unsupported", "hz_3")],
     [GOOD_FID], "temporal_counterexample", "COUNTEREXAMPLE"),
    ([d("inconclusive_budget"), d("within_envelope", "hz_2")], [GOOD_FID],
     "inconclusive_budget", "BUDGET_EXHAUSTED"),
    ([d("inconclusive_budget"), d("unsupported", "hz_2")], [GOOD_FID],
     "inconclusive_budget", "BUDGET_EXHAUSTED"),
    ([d("unsupported"), d("within_envelope", "hz_2")], [GOOD_FID],
     "unsupported_temporal_risk", "UNSUPPORTED"),
    ([d("inconclusive")], [GOOD_FID], "unsupported_temporal_risk", "UNSUPPORTED"),
    ([], [], "no_material_temporal_hazard", "COMPLETED"),
    ([d("projected_boundary", mode="signal"), d("within_envelope", "hz_2")],
     [GOOD_FID], "projected_boundary", "COMPLETED"),
    ([d("within_envelope"), d("bounded_within_envelope", "hz_2", mode="signal")],
     [GOOD_FID], "bounded_future_envelope", "COMPLETED"),
    # The fidelity gate: a clean bill without gates_met is only a boundary.
    ([d("within_envelope")], [BAD_FID], "projected_boundary", "COMPLETED"),
    ([d("within_envelope")], [GOOD_FID, BAD_FID], "projected_boundary", "COMPLETED"),
])
def test_outcome_precedence(tmp_path, dispositions, fids, outcome, state):
    db = Db(str(tmp_path / "ff.db"))
    row = mk_request(db)
    out = results.finalize(db, row, dispositions, fids, SPENT,
                           plan_digest="pd_x", mode="full", seed=7)
    assert out["outcome"] == outcome and out["state"] == state
    row = db.get_request(row["request_id"])
    assert row["state"] == state and row["outcome"] == outcome
    assert row["decided_at"] is not None


def test_envelope_minted_and_verifiable(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    row = mk_request(db)
    out = results.finalize(db, row, [d("within_envelope")], [GOOD_FID], SPENT,
                           plan_digest="pd_x", mode="full", seed=7)
    env = out["envelope"]
    ok, why = envelope.verify(env)
    assert ok, why
    assert env["type"] == "fastforward_result"
    assert env["source"] == "rollout-fastforward"
    assert env["scope"] == {"service": "demo-leak", "episode_id": "ep_t1",
                            "stage": "T+30"}
    assert env["payload"]["hazards"][0]["disposition"] == "within_envelope"
    assert env["payload"]["plan_digest"] == "pd_x"
    # ttl outlives the checkpoint deadline by a day.
    import calendar
    import time as _t

    def parse(ts):
        return calendar.timegm(_t.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    assert parse(env["fresh_until"]) - parse(env["observed_at"]) == 240 + 86400


def test_counterexample_envelope_minted_per_cx(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    row = mk_request(db)
    cx = {"cx_id": "cx_abc123456789", "hazard_id": "hz_1",
          "candidate_digest": "mf_x", "template": "resource_lifecycle_v1",
          "state_slice_digest": "sha256:s", "event_sequence": [],
          "expected_stable": {}, "observed_candidate": {},
          "first_divergence_age": {"cycles": 200}, "replay_seed": 1,
          "replay_verified": True}
    results.finalize(db, row, [d("counterexample")], [GOOD_FID], SPENT,
                     counterexamples=[cx])
    envs = db.envelopes_for_episode("ep_t1")
    types = sorted(e["type"] for e in envs)
    assert types == ["fastforward_result", "temporal_counterexample"]
    cxe = next(e for e in envs if e["type"] == "temporal_counterexample")
    assert cxe["payload"]["cx_id"] == "cx_abc123456789"
    assert envelope.verify(cxe)[0]
    result = next(e for e in envs if e["type"] == "fastforward_result")
    assert result["payload"]["counterexample_ids"] == ["cx_abc123456789"]


def test_snapshot_written_exactly_once(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    row = mk_request(db)
    results.finalize(db, row, [], [], SPENT, plan_digest="pd_x", mode="full",
                     seed=7)
    snap = json.loads(db.get_request(row["request_id"])["snapshot_json"])
    assert set(snap) == {"manifest_digest", "policy_context", "profile_ids",
                         "inventory", "seed", "plan_digest", "mode"}
    assert snap["policy_context"] is None
    with pytest.raises(ValueError):
        db.write_snapshot_once(row["request_id"], {"again": True})


def test_envelopes_withheld_until_terminal_then_queryable(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    row = mk_request(db, state="RUNNING")
    # Even an inserted envelope stays invisible while non-terminal.
    db.insert_envelope(row["request_id"], "ep_t1",
                       envelope.mint("fastforward_result",
                                     {"service": "demo-leak"}, {"x": 1}))
    assert db.envelopes_for_episode("ep_t1") == []
    db.set_state(row["request_id"], "ANALYZING")
    results.finalize(db, db.get_request(row["request_id"]),
                     [d("within_envelope")], [GOOD_FID], SPENT)
    envs = db.envelopes_for_episode("ep_t1")  # late result queryable
    assert len(envs) == 2
    assert all(envelope.verify(e)[0] for e in envs)


def test_degrade_from_any_nonterminal_state(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    for state in ("RECEIVED", "COMPILED", "RUNNING", "ANALYZING"):
        row = mk_request(db, episode=f"ep_{state}", state=state)
        out = results.degrade(db, row, "world unreachable")
        assert out["state"] == "UNSUPPORTED"
        assert out["outcome"] == "unsupported_temporal_risk"
        env = db.envelopes_for_episode(f"ep_{state}")[0]
        assert env["payload"]["reason"] == "world unreachable"
        assert envelope.verify(env)[0]


def test_degrade_never_touches_terminal(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    row = mk_request(db)
    results.finalize(db, row, [], [], SPENT)
    before = db.get_request(row["request_id"])
    results.degrade(db, row["request_id"], "late crash")
    after = db.get_request(row["request_id"])
    assert after["state"] == before["state"] == "COMPLETED"
    assert after["outcome"] == "no_material_temporal_hazard"


def test_dead_probe_target_degrades_never_passes(tmp_path):
    """A hazardous manifest with every upstream dead must land in
    UNSUPPORTED with a signed unsupported_temporal_risk envelope."""
    ff = service.FastForward(str(tmp_path / "ff.db"),
                             world_api="http://127.0.0.1:9",
                             probe_api="http://127.0.0.1:9",
                             observe_api="http://127.0.0.1:9")
    out = ff.submit({"episode_id": "ep_dead", "service": "demo-leak",
                     "deploy_event": LEAK_EVENT, "deadline_s": 60,
                     "budget": {"max_probe_seconds": 30, "max_steps": 4}})
    assert out["state"] == "RECEIVED"
    ff.wait(out["request_id"], timeout=60)
    row = ff.db.get_request(out["request_id"])
    assert row["state"] == "UNSUPPORTED"
    assert row["outcome"] == "unsupported_temporal_risk"
    envs = ff.db.envelopes_for_episode("ep_dead")
    assert len(envs) == 1
    assert envs[0]["payload"]["outcome"] == "unsupported_temporal_risk"
    assert envelope.verify(envs[0])[0]


def test_no_hazard_fast_path_completes(tmp_path):
    """A benign manifest needs no world at all: COMPILED->ANALYZING->COMPLETED."""
    ff = service.FastForward(str(tmp_path / "ff.db"),
                             world_api="http://127.0.0.1:9",
                             probe_api="http://127.0.0.1:9",
                             observe_api="http://127.0.0.1:9")
    out = ff.submit({"episode_id": "ep_benign", "service": "demo-healthy",
                     "deploy_event": {"change_manifest": {"items": [
                         {"kind": "code", "name": "render-refactor",
                          "paths": ["handlers/render.py"]}]}},
                     "deadline_s": 60, "budget": {}})
    ff.wait(out["request_id"], timeout=60)
    row = ff.db.get_request(out["request_id"])
    assert row["state"] == "COMPLETED"
    assert row["outcome"] == "no_material_temporal_hazard"
    envs = ff.db.envelopes_for_episode("ep_benign")
    assert len(envs) == 1 and envs[0]["payload"]["hazards"] == []


def test_fixtures_load_reminted_envelopes(tmp_path):
    ff = service.FastForward(str(tmp_path / "ff.db"))
    body = json.loads((Path(__file__).parent.parent / "fixtures"
                       / "ff-eval-results.json").read_text())
    loaded = ff.load_fixtures(body)
    assert loaded["requests"] == 5
    expect = {"fx-ff-leak": "temporal_counterexample",
              "fx-ff-retry": "temporal_counterexample",
              "fx-ff-cred": "temporal_counterexample",
              "fx-ff-healthy": "no_material_temporal_hazard",
              "fx-ff-budget": "inconclusive_budget"}
    for episode, outcome in expect.items():
        envs = ff.db.envelopes_for_episode(episode)
        assert envs, episode
        result = next(e for e in envs if e["type"] == "fastforward_result")
        assert result["payload"]["outcome"] == outcome
        # Re-minted at load time: signatures are live-key valid.
        assert all(envelope.verify(e)[0] for e in envs)
    cx = ff.db.get_counterexample("cx_a0d5981cfe46")
    assert cx and cx["template"] == "resource_lifecycle_v1"
    # Reload resets cleanly (fixed ids).
    assert ff.load_fixtures(body)["requests"] == 5


def test_seed_profiles_from_clean_world(tmp_path):
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sim"))
    from probe_target import CLEAN_SPEC, ProbeWorld
    ff = service.FastForward(str(tmp_path / "ff.db"))
    out = ff.seed_profiles("demo-leak", target=ProbeWorld(),
                           clean={"spec": dict(CLEAN_SPEC),
                                  "spec_digest": "sha256:cleanfixture"})
    templates = {p["template"] for p in out["profiles"]}
    assert templates == {"resource_lifecycle_v1", "rate_balance_v1",
                         "growth_projection", "queue_drift_projection"}
    from rollout_fastforward.profiles import env_fingerprint
    st = ff.profiles.get("demo-leak", "resource_lifecycle_v1",
                         env_fingerprint({"spec_digest": "sha256:cleanfixture"}))
    assert st["slope_per_cycle"]["median"] == 0.0
