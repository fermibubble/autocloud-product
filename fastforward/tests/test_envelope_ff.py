"""Cross-package contract test: FF-minted envelopes must verify with the
rollout-intel verifier — one shared evidence contract, two signers."""

import calendar
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "intel"))

from rollout_intel import envelope as intel_verifier  # noqa: E402

from rollout_fastforward import envelope as ff  # noqa: E402

SCOPE = {"service": "demo-leak", "episode_id": "ep_1234", "stage": "T+30"}
PAYLOAD = {"outcome": "no_material_temporal_hazard", "request_id": "ffr_1",
           "episode_id": "ep_1234", "service": "demo-leak", "hazards": [],
           "fidelity": {}, "budget": {"granted": 120, "spent": 40},
           "plan_digest": "pd_x", "counterexample_ids": []}


def test_intel_verifier_accepts_ff_envelope():
    env = ff.mint("fastforward_result", SCOPE, PAYLOAD)
    ok, reason = intel_verifier.verify(env)
    assert ok, reason
    assert env["source"] == "rollout-fastforward"


def test_tampered_payload_rejected_by_intel_verifier():
    env = copy.deepcopy(ff.mint("fastforward_result", SCOPE, PAYLOAD))
    env["payload"]["outcome"] = "temporal_counterexample"
    ok, reason = intel_verifier.verify(env)
    assert not ok and reason == "payload hash mismatch"


def test_tampered_signed_field_rejected():
    env = ff.mint("fastforward_result", SCOPE, PAYLOAD)
    env["scope"] = dict(env["scope"], service="other-service")
    ok, reason = intel_verifier.verify(env)
    assert not ok and reason == "bad signature"


def test_scope_carries_plain_service_name():
    # rollout-intel's record() transplant guard matches scope.service against
    # the episode's service — it must be the plain name.
    env = ff.mint("fastforward_result", SCOPE, PAYLOAD)
    assert env["scope"]["service"] == "demo-leak"
    assert env["scope"]["stage"] == "T+30"
    assert env["scope"]["episode_id"] == "ep_1234"


def test_fresh_until_respects_ttl():
    def parse(ts):
        return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))

    ttl = 240 + 86400  # deadline_s + 86400: outlives the checkpoint deadline
    env = ff.mint("fastforward_result", SCOPE, PAYLOAD, ttl_seconds=ttl)
    assert parse(env["fresh_until"]) - parse(env["observed_at"]) == ttl
    ok, _ = intel_verifier.verify(env)
    assert ok


def test_local_verify_matches_intel_verify():
    env = ff.mint("temporal_counterexample", SCOPE, {"cx_id": "cx_1"})
    assert ff.verify(env)[0]
    assert intel_verifier.verify(env)[0]
    env["type"] = "fastforward_result"  # signed field
    assert not ff.verify(env)[0]
    assert not intel_verifier.verify(env)[0]
