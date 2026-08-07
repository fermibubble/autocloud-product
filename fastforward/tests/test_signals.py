"""Signal tests: a rising verified series projects a boundary, a flat one
is bounded — and WITHOUT a stable profile nothing ever passes by default."""

import copy
import time

import pytest

from rollout_fastforward import envelope, signals
from rollout_fastforward.db import Db
from rollout_fastforward.profiles import ProfileStore

SERVICE = "demo-leak"
STEP = {"hazard_id": "hz_x", "mode": "signal", "template": "growth_projection"}
QSTEP = {"hazard_id": "hz_y", "mode": "signal", "template": "queue_drift_projection"}
HAZARD = {"hazard_id": "hz_x", "class": "resource_lifecycle", "min_fidelity": {}}

OPEN = "run.googleapis.com/container/open_connections"
QUEUE = "run.googleapis.com/container/queue_depth"
RETRY = "run.googleapis.com/container/retry_count"

RISING = [40.0 + 2.0 * i for i in range(11)]          # 2/min toward the level
FLAT = [40.0 + 0.03 * (i % 3) for i in range(11)]     # jitter well inside MAD


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def mk_env(metric_type, values, service=SERVICE):
    t0 = time.time() - 60 * len(values)
    points = [{"end": _iso(t0 + 60 * i), "value": v} for i, v in enumerate(values)]
    return envelope.mint(
        "metric_window",
        {"project": "sim-project", "region": "us-central1", "service": service},
        {"metric_type": metric_type, "series": [
            {"metric": metric_type, "labels": {"service_name": service},
             "points": points}]},
        {"completeness": "COMPLETE", "sample_count": 999, "window_minutes": 30})


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def patch_fetch(monkeypatch, envs_by_type):
    def fake_get(url, params=None, timeout=None):
        return FakeResp(envs_by_type[params["type"]])
    monkeypatch.setattr(signals.httpx, "get", fake_get)


@pytest.fixture
def store(tmp_path):
    s = ProfileStore(Db(str(tmp_path / "ff.db")))
    flat = {"slope": {"median": 0.0, "mad": 0.05, "n": 11}}
    s.put(SERVICE, "growth_projection", signals.SIGNAL_FP, flat)
    s.put(SERVICE, "queue_drift_projection", signals.SIGNAL_FP, flat)
    return s


def test_rising_series_projects_boundary(monkeypatch, store):
    patch_fetch(monkeypatch, {OPEN: mk_env(OPEN, RISING)})
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "projected_boundary"
    m = res["measurements"]
    assert m["z_lo"] > signals.Z_HARM
    assert 0 < m["time_to_threshold_min"] < signals.HORIZON_MIN
    assert len(res["observation_ids"]) == 1


def test_flat_series_is_bounded(monkeypatch, store):
    patch_fetch(monkeypatch, {OPEN: mk_env(OPEN, FLAT)})
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "bounded_within_envelope"


def test_missing_profile_never_passes(monkeypatch, tmp_path):
    empty = ProfileStore(Db(str(tmp_path / "empty.db")))
    for values in (RISING, FLAT):
        patch_fetch(monkeypatch, {OPEN: mk_env(OPEN, values)})
        res = signals.run_signal(STEP, HAZARD, SERVICE, empty, None)
        assert res["disposition"] == "inconclusive_signal"
        assert "profile" in res["reason"]


def test_queue_drift_needs_both_metrics_rising(monkeypatch, store):
    patch_fetch(monkeypatch, {QUEUE: mk_env(QUEUE, RISING),
                              RETRY: mk_env(RETRY, RISING)})
    res = signals.run_signal(QSTEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "projected_boundary"
    # Rising queue with FLAT retries is uncorroborated -> not a boundary call.
    patch_fetch(monkeypatch, {QUEUE: mk_env(QUEUE, RISING),
                              RETRY: mk_env(RETRY, FLAT)})
    res = signals.run_signal(QSTEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "inconclusive_signal"


def test_tampered_envelope_is_inconclusive(monkeypatch, store):
    env = copy.deepcopy(mk_env(OPEN, RISING))
    env["payload"]["series"][0]["points"][-1]["value"] = 9999.0  # forge a spike
    patch_fetch(monkeypatch, {OPEN: env})
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "inconclusive_signal"
    assert "unverified" in res["reason"]


def test_foreign_scope_is_inconclusive(monkeypatch, store):
    patch_fetch(monkeypatch, {OPEN: mk_env(OPEN, RISING, service="other-svc")})
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "inconclusive_signal"


def test_fetch_failure_is_inconclusive(monkeypatch, store):
    def boom(url, params=None, timeout=None):
        raise ConnectionError("probe down")
    monkeypatch.setattr(signals.httpx, "get", boom)
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "inconclusive_signal"
    assert "fetch failed" in res["reason"]


def test_window_predating_deploy_never_certifies_flat(monkeypatch, store):
    # A FLAT window whose points nearly all predate the deploy describes the
    # OLD revision — it must escalate, not pass the candidate.
    patch_fetch(monkeypatch, {OPEN: mk_env(OPEN, FLAT)})
    recent_deploy = time.time() - 90  # only the last point or two are ours
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None,
                             deployed_at=recent_deploy)
    assert res["disposition"] == "inconclusive_signal"
    assert "post-deploy" in res["reason"]
    # An old deploy leaves the whole window as candidate evidence.
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None,
                             deployed_at=time.time() - 3600)
    assert res["disposition"] == "bounded_within_envelope"


def test_too_few_points_is_inconclusive(monkeypatch, store):
    patch_fetch(monkeypatch, {OPEN: mk_env(OPEN, [40.0, 42.0])})
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "inconclusive_signal"


def test_deadline_passed_is_inconclusive(store):
    res = signals.run_signal(STEP, HAZARD, SERVICE, store, time.time() - 10)
    assert res["disposition"] == "inconclusive_signal"


def test_unknown_template_is_inconclusive(store):
    res = signals.run_signal({"template": "nope"}, HAZARD, SERVICE, store, None)
    assert res["disposition"] == "inconclusive_signal"
