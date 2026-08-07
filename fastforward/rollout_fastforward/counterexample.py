"""Temporal counterexamples: the minimal replayable event sequence under
which the candidate diverges from stable behavior.

MVP minimization = the playbook action log, which is already small. Replay
re-creates an instance with the same seed+spec (both live verbatim in the
log's create action), re-drives the sequence, and asserts the divergence
recurs at the same first_divergence_age — the probe target's determinism
contract makes this byte-exact, so any tampering with the sequence fails.
"""

import hashlib
import json


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def events_digest(events: list[dict]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(events)).hexdigest()


def make_cx_id(manifest_digest: str, hazard_id: str, template: str) -> str:
    basis = f"{manifest_digest}|{hazard_id}|{template}"
    return "cx_" + hashlib.sha256(basis.encode()).hexdigest()[:12]


def build(request: dict, hazard: dict, template: str, probe_events: list[dict],
          expected_stable, observed_candidate, first_divergence_age,
          seed: int, spec_digest: str) -> dict:
    """Counterexample artifact. probe_events is the session action log,
    replayed VERBATIM; candidate_digest pins the manifest, state_slice_digest
    pins the behavior spec the replica ran under."""
    mdig = request.get("manifest_digest", "")
    return {
        "cx_id": make_cx_id(mdig, hazard.get("hazard_id", ""), template),
        "hazard_id": hazard.get("hazard_id"),
        "candidate_digest": mdig,
        "template": template,
        "state_slice_digest": spec_digest,
        "event_sequence": list(probe_events),
        "expected_stable": expected_stable,
        "observed_candidate": observed_candidate,
        "first_divergence_age": first_divergence_age,
        "replay_seed": seed,
        "replay_verified": False,
    }


def _divergence_age(cx: dict, events: list[dict]):
    """Where the replayed run diverged, per template semantics."""
    if cx.get("template") == "cred_lifecycle_v1":
        for e in events:
            if e.get("kind") == "stale_credential_reuse":
                return e.get("age")
        return None
    seq = (cx.get("observed_candidate") or {}).get("divergence_event_seq")
    if seq is not None:
        for e in events:
            if e.get("seq") == seq:
                return e.get("age")
    return None


def replay(cx: dict, target) -> tuple[bool, dict]:
    """Re-drive the event sequence against target (PROBE_API base URL or an
    in-process ProbeWorld) -> (verified, observed). Verified only when the
    replayed events are byte-identical AND the divergence recurs at the same
    first_divergence_age."""
    from .probes import ProbeSession  # local: probes builds on nothing here

    session = ProbeSession(target)
    try:
        for action in cx.get("event_sequence", []):
            session.apply(action)
        events = session.events()
    finally:
        try:
            session.destroy()
        except Exception:
            pass
    digest = events_digest(events)
    age = _divergence_age(cx, events)
    expected_digest = (cx.get("observed_candidate") or {}).get("events_digest")
    verified = (digest == expected_digest
                and age == cx.get("first_divergence_age")
                and age is not None)
    return verified, {"events_digest": digest, "first_divergence_age": age}
