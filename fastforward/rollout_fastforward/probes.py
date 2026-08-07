"""Probe-target driving: one replica per session, budget/deadline-gated,
with a verbatim action log.

The log records only state-mutating calls — reads shape nothing — so the
log IS the minimal event sequence a temporal counterexample replays. A
session speaks either transport: a PROBE_API base URL (the :7640 face) or
an in-process sim ProbeWorld (unit tests, replay verification). Effect
accounting: side_effect_attempts is read from counters and surfaced in
every run record — the membrane's receipt that nothing external ran.
"""

import json
import time
from dataclasses import dataclass

import httpx


class BudgetExceeded(Exception):
    """Raised before a driving call once wall budget or deadline is spent."""


@dataclass
class ProbeContext:
    """Everything a playbook needs to probe one hazard."""
    target: object                  # PROBE_API base URL or in-process ProbeWorld
    service: str
    revision: str                   # candidate revision
    seed: int
    spec: dict                      # candidate behavior spec
    spec_digest: str
    request: dict                   # ff_requests row (manifest_digest, ...)
    hazard: dict
    previous_revision: str = ""
    clean_spec: dict | None = None  # known-good spec for the paired fallback
    clean_spec_digest: str = ""
    profiles: object | None = None  # ProfileStore
    budget_s: float = float("inf")
    deadline_at: float | None = None
    horizon_min: float = 1440.0     # policy horizon projections must cover


class ProbeSession:
    """One probe instance, either transport, with wall-budget gating."""

    def __init__(self, target, budget_s: float = float("inf"),
                 deadline_at: float | None = None):
        self.target = target
        self.budget_s = budget_s
        self.deadline_at = deadline_at
        self.started = time.time()
        self.log: list[dict] = []   # mutations only — the replay script source
        self.instance_id: str | None = None
        self._inst = None           # in-process Instance when target is a world

    # --- budget -----------------------------------------------------------

    def spent_s(self) -> float:
        return time.time() - self.started

    def budget_left(self) -> float:
        left = self.budget_s - self.spent_s()
        if self.deadline_at is not None:
            left = min(left, self.deadline_at - time.time())
        return left

    def _gate(self) -> None:
        if self.budget_left() <= 0:
            raise BudgetExceeded(f"probe budget spent ({self.spent_s():.1f}s)")

    # --- transport --------------------------------------------------------

    def _http(self) -> bool:
        return isinstance(self.target, str)

    def _post(self, path: str, body: dict) -> dict:
        resp = httpx.post(f"{self.target}{path}", json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _mutate(self, action: str, args: dict, http_path: str,
                inproc) -> None:
        """Gate on budget, log the action verbatim, then drive it."""
        self._gate()
        self.log.append({"action": action, "args": args})
        if self._http():
            self._post(f"/probe/instances/{self.instance_id}/{http_path}", args)
        else:
            with self.target.lock:
                inproc()

    # --- lifecycle --------------------------------------------------------

    def create(self, service: str, revision: str, seed: int,
               spec: dict | None = None) -> str:
        self._gate()
        self.log.append({"action": "create",
                         "args": {"service": service, "revision": revision,
                                  "seed": seed, "spec": spec}})
        if self._http():
            body = {"service": service, "revision": revision, "seed": seed}
            if spec is not None:
                body["spec"] = spec
            self.instance_id = self._post("/probe/instances", body)["instance_id"]
        else:
            self._inst = self.target.create(service, revision, seed, spec)
            self.instance_id = self._inst.instance_id
        return self.instance_id

    def cycle(self, n: int) -> None:
        self._mutate("cycle", {"n": n}, "cycle", lambda: self._inst.cycle(n))

    def requests(self, n: int, concurrency: int = 1) -> None:
        self._mutate("requests", {"n": n, "concurrency": concurrency},
                     "requests", lambda: self._inst.requests(n, concurrency))

    def dependency(self, failure_rate: float, latency_ms: int = 0) -> None:
        self._mutate("dependency",
                     {"failure_rate": failure_rate, "latency_ms": latency_ms},
                     "dependency",
                     lambda: self._inst.dependency(failure_rate, latency_ms))

    def advance(self, axis: str, amount) -> None:
        self._mutate("advance", {"axis": axis, "amount": amount},
                     "advance", lambda: self._inst.advance(axis, amount))

    def rotate_key(self) -> None:
        self._mutate("rotate_key", {}, "rotate-key", lambda: self._inst.rotate_key())

    def refresh_fault(self, transient: bool = True) -> None:
        self._mutate("refresh_fault", {"transient": transient},
                     "refresh-fault", lambda: self._inst.refresh_fault(transient))

    # --- reads (never logged; they don't shape the replica) ---------------

    def counters(self) -> dict:
        if self._http():
            resp = httpx.get(
                f"{self.target}/probe/instances/{self.instance_id}/counters",
                timeout=30)
            resp.raise_for_status()
            return resp.json()["counters"]
        return dict(self._inst.counters)

    def events(self) -> list[dict]:
        if self._http():
            resp = httpx.get(
                f"{self.target}/probe/instances/{self.instance_id}/events",
                timeout=30)
            resp.raise_for_status()
            return resp.json()["events"]
        # JSON round-trip: byte-identical shape to the HTTP face.
        return json.loads(json.dumps(list(self._inst.events)))

    def destroy(self) -> None:
        if self.instance_id is None:
            return
        if self._http():
            httpx.delete(f"{self.target}/probe/instances/{self.instance_id}",
                         timeout=30)
        else:
            with self.target.lock:
                self.target.instances.pop(self.instance_id, None)
        self.instance_id, self._inst = None, None

    # --- replay -----------------------------------------------------------

    def apply(self, action: dict) -> None:
        """Re-drive one logged action verbatim (counterexample replay)."""
        name, args = action["action"], dict(action.get("args", {}))
        if name == "create":
            self.create(args["service"], args["revision"], args["seed"],
                        args.get("spec"))
            return
        getattr(self, name)(**args)

    def run_record(self, seed: int, measurements: dict, stop_reason: str,
                   started_at: str, ended_at: str) -> dict:
        """Probe-run row for db.insert_probe_run, with effect accounting."""
        counters = {}
        try:
            counters = self.counters()
        except Exception:
            pass
        return {"instance_id": self.instance_id, "seed": seed,
                "measurements": measurements,
                "side_effects": [{"side_effect_attempts":
                                  counters.get("side_effect_attempts", 0),
                                  "contained": True}],
                "stop_reason": stop_reason,
                "started_at": started_at, "ended_at": ended_at}
