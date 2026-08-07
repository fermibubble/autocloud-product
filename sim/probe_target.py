"""probe-target: deterministic accelerated replicas for Fast-Forward.

Fast-Forward compresses a candidate revision's future by driving a probe
replica through orders of STATE (connection cycles, request batches,
credential age) instead of wall-clock time. Each instance is a pure
function of (seed, spec, call sequence): the same three inputs yield
byte-identical counters and events, which is what makes temporal
counterexamples replayable.

The behavior spec comes from the world face
(GET {WORLD_API}/world/probe-spec?service=NAME&revision=REV — the CURRENT
candidate revision carries the seeded bug, the previous revision is clean)
or inline via a "spec" key in the create body for in-process tests.

Effect membrane invariant: an instance NEVER touches anything external —
no sockets to dependencies, no credential issuers, no key-management APIs.
Every operation that WOULD (a request batch, a connection cycle, a key
rotation, a credential refresh) only increments side_effect_attempts.
This is the effect membrane in sim form.

HTTP face (:7640):
  POST   /probe/instances                     {service, revision, seed[, spec]}
  POST   /probe/instances/{id}/cycle          {n}
  POST   /probe/instances/{id}/requests       {n, concurrency}
  POST   /probe/instances/{id}/dependency     {failure_rate, latency_ms}
  POST   /probe/instances/{id}/advance        {axis: cred_age_s|wall_s, amount}
  POST   /probe/instances/{id}/rotate-key     {}
  POST   /probe/instances/{id}/refresh-fault  {transient}
  GET    /probe/instances/{id}/counters
  GET    /probe/instances/{id}/events
  DELETE /probe/instances/{id}

Run:  WORLD_API=http://127.0.0.1:7621 uv run python probe_target.py
"""

import argparse
import json
import os
import random
import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse

WORLD_API = os.environ.get("WORLD_API", "http://127.0.0.1:7621")

# What a clean (previous-revision / legacy-service) replica behaves like;
# inline or fetched specs overlay these defaults.
CLEAN_SPEC = {"conn_leak_per_cycle": 0, "retry_p_f": 0.05, "retry_e_k": 1,
              "cred_ttl_s": 3600, "reuse_after_rotate_bug": False}

WARM_POOL_MAX = 10   # clean transient: pooled warm connections plateau here
LEAK_PER = 100.0     # conn_leak_per_cycle is handles leaked per 100 cycles

COUNTER_KEYS = ("open_handles", "queue_depth", "requests", "retries",
                "failures", "cycles", "cred_age_s", "rotations",
                "refresh_failures", "stale_reuse_count", "side_effect_attempts")


class Instance:
    """One probe replica. Every transition is deterministic in (seed, spec,
    call sequence); rng draws happen in a fixed order per call."""

    def __init__(self, instance_id: str, service: str, revision: str,
                 seed: int, spec: dict | None):
        self.instance_id = instance_id
        self.service = service
        self.revision = revision
        self.seed = seed
        self.spec = {**CLEAN_SPEC, **(spec or {})}
        self.rng = random.Random(seed)
        self.counters = {k: 0 for k in COUNTER_KEYS}
        self.events: list[dict] = []
        self._seq = 0
        self._leak_acc = 0.0     # fractional leaked handles, rounded down
        self._warm = 0           # warm pooled connections (plateaus)
        self._key_epoch = 0      # advanced by rotate-key
        self._cred_epoch = 0     # key epoch the held credential was minted at
        self._refresh_fault = False
        self._dep_failure_rate = 0.0
        self._dep_latency_ms = 0
        self._wall_s = 0

    def _event(self, kind: str, detail) -> None:
        self._seq += 1
        c = self.counters
        self.events.append({"seq": self._seq, "kind": kind, "detail": detail,
                            "age": {"cycles": c["cycles"], "requests": c["requests"],
                                    "retries": c["retries"],
                                    "cred_age_s": c["cred_age_s"],
                                    "rotations": c["rotations"]}})

    def cycle(self, n: int) -> None:
        """n connection open/use/close lifecycles. A buggy spec leaks
        conn_leak_per_cycle handles per 100 cycles (float-accumulated,
        deterministically rounded); a clean spec only warms the pool."""
        c = self.counters
        c["cycles"] += n
        c["side_effect_attempts"] += 1  # would open connections to a dependency
        self._leak_acc += n * self.spec["conn_leak_per_cycle"] / LEAK_PER
        leaked = int(self._leak_acc)
        self._leak_acc -= leaked
        warm_delta = min(WARM_POOL_MAX - self._warm, n)
        self._warm += warm_delta
        c["open_handles"] += leaked + warm_delta
        self._event("cycle", n)

    def requests(self, n: int, concurrency: int) -> None:
        """A batch of n requests. Dependency failures (seeded rng around the
        dialed rate) spawn retries with multiplier m = retry_p_f * retry_e_k;
        m >= 1 under failures grows the queue, otherwise it drains. A rotated
        key plus an expired credential either reuses the stale credential
        (the seeded bug: auth timeouts) or re-authenticates (clean)."""
        c, spec = self.counters, self.spec
        c["requests"] += n
        c["side_effect_attempts"] += 1  # would call the downstream dependency
        if self._key_epoch > self._cred_epoch and c["cred_age_s"] > spec["cred_ttl_s"]:
            if spec["reuse_after_rotate_bug"]:
                c["stale_reuse_count"] += 1
                c["failures"] += n  # whole batch auth-times-out on the stale cred
                self._event("stale_credential_reuse", {"n": n})
            else:
                self._refresh()
        expected = n * self._dep_failure_rate
        fail = int(expected) + (1 if self.rng.random() < expected - int(expected) else 0)
        m = spec["retry_p_f"] * spec["retry_e_k"]
        retr = round(fail * m)
        c["failures"] += fail
        c["retries"] += retr
        if m >= 1 and self._dep_failure_rate > 0:
            c["queue_depth"] += round(n * self._dep_failure_rate * m)  # amplifying
        else:
            c["queue_depth"] = max(0, c["queue_depth"] - max(1, n // 10))  # drains
        self._event("requests", {"n": n, "concurrency": concurrency,
                                 "failures": fail, "retries": retr})

    def _refresh(self) -> None:
        c = self.counters
        c["side_effect_attempts"] += 1  # would hit the credential issuer
        if self._refresh_fault:
            self._refresh_fault = False  # transient: fails once, then recovers
            c["refresh_failures"] += 1
            self._event("credential_refresh_failed", {"transient": True})
            return
        self._cred_epoch = self._key_epoch
        c["cred_age_s"] = 0
        self._event("credential_refresh", {"epoch": self._cred_epoch})

    def dependency(self, failure_rate: float, latency_ms: int) -> None:
        self._dep_failure_rate = float(failure_rate)
        self._dep_latency_ms = int(latency_ms)
        self._event("dependency", {"failure_rate": self._dep_failure_rate,
                                   "latency_ms": self._dep_latency_ms})

    def advance(self, axis: str, amount) -> None:
        if axis == "cred_age_s":
            self.counters["cred_age_s"] += int(amount)
        elif axis == "wall_s":
            self._wall_s += int(amount)
        else:
            raise ValueError(f"unknown axis {axis!r}")
        self._event("advance", {"axis": axis, "amount": int(amount)})

    def rotate_key(self) -> None:
        c = self.counters
        c["rotations"] += 1
        c["side_effect_attempts"] += 1  # would call the key-management API
        self._key_epoch += 1
        self._event("rotate_key", {"epoch": self._key_epoch})

    def refresh_fault(self, transient: bool = True) -> None:
        self._refresh_fault = True
        self._event("refresh_fault", {"transient": bool(transient)})


class ProbeWorld:
    def __init__(self):
        self.lock = threading.Lock()
        self.instances: dict[str, Instance] = {}
        self._next = 0

    def create(self, service: str, revision: str, seed: int,
               spec: dict | None = None) -> Instance:
        if spec is None:
            spec = self._fetch_spec(service, revision)
        with self.lock:
            self._next += 1
            inst = Instance(f"pi-{self._next:08d}", service, revision, seed, spec)
            self.instances[inst.instance_id] = inst
        return inst

    @staticmethod
    def _fetch_spec(service: str, revision: str) -> dict:
        qs = urlencode({"service": service, "revision": revision})
        with urllib.request.urlopen(f"{WORLD_API}/world/probe-spec?{qs}",
                                    timeout=10) as resp:
            return json.load(resp)["spec"]


# --- HTTP face (:7640) ------------------------------------------------------

_ROUTE = re.compile(r"^/probe/instances/([^/]+)(?:/([a-z-]+))?$")


class ProbeFace(BaseHTTPRequestHandler):
    world: ProbeWorld

    def _send(self, code: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def _instance(self, path: str) -> tuple[Instance | None, str | None]:
        m = _ROUTE.match(path)
        if not m:
            return None, None
        return self.world.instances.get(m.group(1)), m.group(2)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/probe/instances":
            body = self._body()
            try:
                inst = self.world.create(body.get("service", ""),
                                         body.get("revision", ""),
                                         int(body.get("seed", 0)),
                                         body.get("spec"))
            except Exception as exc:  # spec fetch failed — report, don't guess
                self._send(502, {"error": f"probe-spec unavailable: {exc}"})
                return
            self._send(200, {"instance_id": inst.instance_id})
            return
        inst, action = self._instance(path)
        if inst is None or action is None:
            self._send(404, {"error": f"unknown path {path}"})
            return
        body = self._body()
        try:
            with self.world.lock:
                if action == "cycle":
                    inst.cycle(int(body.get("n", 1)))
                elif action == "requests":
                    inst.requests(int(body.get("n", 1)),
                                  int(body.get("concurrency", 1)))
                elif action == "dependency":
                    inst.dependency(body.get("failure_rate", 0.0),
                                    body.get("latency_ms", 0))
                elif action == "advance":
                    inst.advance(body.get("axis", ""), body.get("amount", 0))
                elif action == "rotate-key":
                    inst.rotate_key()
                elif action == "refresh-fault":
                    inst.refresh_fault(body.get("transient", True))
                else:
                    self._send(404, {"error": f"unknown action {action}"})
                    return
        except (ValueError, TypeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        self._send(200, {"ok": True, "counters": dict(inst.counters)})

    def do_GET(self):  # noqa: N802
        inst, action = self._instance(urlparse(self.path).path)
        if inst is None:
            self._send(404, {"error": "unknown instance"})
        elif action == "counters":
            self._send(200, {"counters": dict(inst.counters)})
        elif action == "events":
            self._send(200, {"events": list(inst.events)})
        else:
            self._send(404, {"error": f"unknown action {action}"})

    def do_DELETE(self):  # noqa: N802
        m = _ROUTE.match(urlparse(self.path).path)
        if not m or m.group(2) or m.group(1) not in self.world.instances:
            self._send(404, {"error": "unknown instance"})
            return
        with self.world.lock:
            self.world.instances.pop(m.group(1), None)
        self._send(200, {"deleted": True})

    def log_message(self, *args):
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7640)
    args = ap.parse_args()
    world = ProbeWorld()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port),
                              type("Face", (ProbeFace,), {"world": world}))
    print(f"probe-target: :{args.port} world={WORLD_API} (deterministic, no external effects)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
