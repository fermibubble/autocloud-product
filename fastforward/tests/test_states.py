"""State-machine and Db integrity tests: legal walks, illegal transitions,
terminal immutability, write-once snapshots, terminal-gated envelopes."""

import pytest

from rollout_fastforward import envelope as ff_envelope
from rollout_fastforward import states
from rollout_fastforward.db import Db

MANIFEST = {"items": [{"kind": "dependency", "name": "pg-pool",
                       "from": "2.1.0", "to": "3.0.0"}]}


def make_request(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    row = db.create_request("ep_1", "demo-leak", MANIFEST, 240.0,
                            {"max_probe_seconds": 120, "max_steps": 40})
    return db, row["request_id"]


def test_full_legal_walk(tmp_path):
    db, rid = make_request(tmp_path)
    assert db.get_request(rid)["state"] == "RECEIVED"
    for s in ("COMPILED", "PLANNED", "RUNNING", "ANALYZING", "COMPLETED"):
        assert db.set_state(rid, s)["state"] == s
    assert db.get_request(rid)["decided_at"] is not None


def test_no_hazard_fast_path(tmp_path):
    db, rid = make_request(tmp_path)
    db.set_state(rid, "COMPILED")
    assert db.set_state(rid, "ANALYZING")["state"] == "ANALYZING"


def test_illegal_transitions_raise():
    cases = [("RECEIVED", "RUNNING"), ("RECEIVED", "COMPLETED"),
             ("COMPILED", "RUNNING"), ("PLANNED", "ANALYZING"),
             ("RUNNING", "COMPLETED"), ("ANALYZING", "PLANNED"),
             ("RECEIVED", "RECEIVED")]
    for cur, new in cases:
        with pytest.raises(ValueError):
            states.validate_transition(cur, new)
    with pytest.raises(ValueError):
        states.validate_transition("RECEIVED", "NOT_A_STATE")
    with pytest.raises(ValueError):
        states.validate_transition("NOT_A_STATE", "COMPILED")


def test_any_nonterminal_can_bail_out():
    for cur in ("RECEIVED", "COMPILED", "PLANNED", "RUNNING", "ANALYZING"):
        states.validate_transition(cur, "UNSUPPORTED")
        states.validate_transition(cur, "CANCELED")


def test_terminal_states_are_immutable(tmp_path):
    db, rid = make_request(tmp_path)
    db.set_state(rid, "CANCELED")
    for new in states.STATES:
        with pytest.raises(ValueError):
            db.set_state(rid, new)
    assert db.get_request(rid)["state"] == "CANCELED"


def test_analyzing_terminals(tmp_path):
    for terminal in ("COMPLETED", "COUNTEREXAMPLE", "BUDGET_EXHAUSTED"):
        states.validate_transition("ANALYZING", terminal)


def test_snapshot_written_exactly_once(tmp_path):
    db, rid = make_request(tmp_path)
    db.write_snapshot_once(rid, {"decided": "pass"})
    with pytest.raises(ValueError):
        db.write_snapshot_once(rid, {"decided": "overwrite"})
    import json
    assert json.loads(db.get_request(rid)["snapshot_json"]) == {"decided": "pass"}


def test_set_state_unknown_request_raises(tmp_path):
    db = Db(str(tmp_path / "ff.db"))
    with pytest.raises(ValueError):
        db.set_state("ffr_missing", "COMPILED")


def test_envelopes_only_leave_when_terminal(tmp_path):
    db, rid = make_request(tmp_path)
    env = ff_envelope.mint(
        "fastforward_result",
        {"service": "demo-leak", "episode_id": "ep_1", "stage": "T+30"},
        {"outcome": "no_material_temporal_hazard"})
    db.insert_envelope(rid, "ep_1", env)
    assert db.envelopes_for_episode("ep_1") == []  # non-terminal: withheld
    assert db.envelopes_for_episode("ep_1", terminal_only=False) == [env]
    db.set_state(rid, "COMPILED")
    db.set_state(rid, "ANALYZING")
    db.set_state(rid, "COMPLETED")
    assert db.envelopes_for_episode("ep_1") == [env]
