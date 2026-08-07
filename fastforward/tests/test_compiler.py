"""Compiler tests: every MVP signature fires on its traits, the floor is
deterministic, and proposals can never remove or downgrade it."""

from rollout_fastforward import compiler, inventory

CAPS = inventory.capabilities()

LEAK = {"items": [{"kind": "dependency", "name": "pg-pool", "from": "2.1.0", "to": "3.0.0"}]}
RETRY = {"items": [{"kind": "config", "name": "retry_max", "from": 1, "to": 4}]}
CRED = {"items": [{"kind": "dependency", "name": "auth-client", "from": "5.2", "to": "6.0"}]}
SCHEMA = {"items": [{"kind": "schema", "name": "orders", "from": "v3", "to": "v4"}]}
CRON = {"items": [{"kind": "code", "name": "jobs", "paths": ["jobs/cron_runner.py"]}]}
AGENT = {"items": [{"kind": "flag", "name": "agent-memory-v2", "from": False, "to": True}]}
BENIGN = {"items": [{"kind": "code", "name": "render", "paths": ["handlers/render.py"]}]}


def classes(hazards):
    return sorted(h["class"] for h in hazards)


def test_resource_lifecycle_fires_on_pool_dep():
    hz = compiler.compile(LEAK, CAPS)
    assert classes(hz) == ["resource_lifecycle"]
    h = hz[0]
    assert h["source"] == "floor"
    assert h["experiments"] == ["signal:growth_projection", "probe:resource_lifecycle_v1"]
    assert h["executable_experiments"] == h["experiments"]
    assert h["expected_symptom"] == "positive_persistent_growth:open_handles"
    assert h["age_dimensions"] == ["connection_cycles", "requests"]
    assert h["impact"] == "high" and h["decision_relevance"] == 0.9


def test_rate_balance_fires_on_retry_config():
    hz = compiler.compile(RETRY, CAPS)
    assert classes(hz) == ["rate_balance"]
    assert hz[0]["experiments"] == ["signal:queue_drift_projection", "probe:rate_balance_v1"]
    assert hz[0]["decision_relevance"] == 0.85


def test_clock_expiry_is_probe_only():
    # No signal experiment by design: expiry bugs are event-sequence-only,
    # so a signal-only arm structurally cannot see them.
    hz = compiler.compile(CRED, CAPS)
    assert classes(hz) == ["clock_expiry"]
    assert hz[0]["experiments"] == ["probe:cred_lifecycle_v1"]
    assert not any(e.startswith("signal:") for e in hz[0]["experiments"])


def test_unsupported_classes_compile_with_no_experiments():
    for m, klass in ((SCHEMA, "state_boundary"), (CRON, "concurrency"),
                     (AGENT, "agent_longevity")):
        hz = compiler.compile(m, CAPS)
        assert classes(hz) == [klass]
        assert hz[0]["experiments"] == []
        assert hz[0]["executable_experiments"] == []


def test_benign_manifest_yields_zero_hazards():
    assert compiler.compile(BENIGN, CAPS) == []


def test_hazard_ids_are_deterministic():
    a = compiler.compile(LEAK, CAPS)
    b = compiler.compile(LEAK, CAPS)
    assert [h["hazard_id"] for h in a] == [h["hazard_id"] for h in b]
    assert all(h["hazard_id"].startswith("hz_") for h in a)
    # Different manifest -> different id even for the same class.
    other = {"items": [{"kind": "config", "name": "pool_size", "from": 10, "to": 50}]}
    assert compiler.compile(other, CAPS)[0]["hazard_id"] != a[0]["hazard_id"]


def test_merge_proposals_cannot_remove_floor():
    floor = compiler.compile(LEAK, CAPS)
    hid = floor[0]["hazard_id"]
    merged, rejected = compiler.merge_proposals(
        floor, [{"hazard_id": hid, "action": "remove"}])
    assert [h["hazard_id"] for h in merged] == [hid]
    assert len(rejected) == 1


def test_merge_proposals_cannot_downgrade_floor():
    floor = compiler.compile(LEAK, CAPS)
    hid = floor[0]["hazard_id"]
    merged, rejected = compiler.merge_proposals(
        floor, [{"hazard_id": hid, "decision_relevance": 0.1}])
    assert merged[0]["decision_relevance"] == 0.9
    assert len(rejected) == 1


def test_merge_proposals_can_raise_relevance_and_add():
    floor = compiler.compile(LEAK, CAPS)
    hid = floor[0]["hazard_id"]
    merged, rejected = compiler.merge_proposals(floor, [
        {"hazard_id": hid, "decision_relevance": 0.95},
        {"hazard_id": "hz_proposed0000000", "class": "rate_balance",
         "features": ["cfg-class:retry"], "decision_relevance": 0.7},
    ])
    assert rejected == []
    by_id = {h["hazard_id"]: h for h in merged}
    assert by_id[hid]["decision_relevance"] == 0.95
    assert by_id[hid]["source"] == "floor"
    assert by_id["hz_proposed0000000"]["source"] == "proposed"


def test_merge_proposals_rejects_unknown_class():
    floor = compiler.compile(LEAK, CAPS)
    merged, rejected = compiler.merge_proposals(
        floor, [{"hazard_id": "hz_x", "class": "made_up"}])
    assert len(merged) == 1 and len(rejected) == 1
