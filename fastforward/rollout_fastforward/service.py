"""rollout-fastforward: the Fast-Forward temporal-evidence service.

Two faces, one SQLite state (the rollout-intel pattern):
  - MCP (:7630) — read-only tools for reviewer agents: get_hazard_report,
    get_fastforward_result (signed envelopes verbatim), get_counterexample.
  - REST (:7631) — request submission and lifecycle, result envelopes for
    rollout-intel's run_stage_checks, replay, profile seeding, fixtures.

POST /ff/requests returns immediately; a daemon worker thread walks the
state machine (compile -> plan -> run -> analyze -> finalize). The ENTIRE
worker body lands in results.degrade on any exception — a dead probe
target yields unsupported_temporal_risk, never a pass. Seeds derive
deterministically: seed = int(sha256(manifest_digest + hazard_id)[:8], 16),
so the same world state replays identically.

Run: FF_DB=ff.db uv run --project . python -m rollout_fastforward.service \
       --mcp-port 7630 --rest-port 7631
"""

import argparse
import calendar
import hashlib
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

from . import compiler, counterexample, envelope, inventory, planner, playbooks, results, signals
from .db import Db, now_iso
from .probes import ProbeContext, ProbeSession
from .profiles import ProfileStore, env_fingerprint
from .stats import mad
from .states import STATES, TERMINAL


def _epoch(iso: str | None) -> float | None:
    if not iso:
        return None
    return float(calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")))


def derive_seed(manifest_digest: str, hazard_id: str = "") -> int:
    return int(hashlib.sha256((manifest_digest + hazard_id).encode())
               .hexdigest()[:8], 16)


class FastForward:
    def __init__(self, db_path: str, world_api: str | None = None,
                 probe_api: str | None = None, observe_api: str | None = None,
                 mode: str | None = None):
        self.db_path = db_path
        self.db = Db(db_path)
        self.world_api = world_api or os.environ.get("WORLD_API",
                                                     "http://127.0.0.1:7621")
        self.probe_api = probe_api or os.environ.get("PROBE_API",
                                                     "http://127.0.0.1:7640")
        self.observe_api = observe_api or os.environ.get("OBSERVE_API",
                                                         "http://127.0.0.1:7601")
        self.mode = mode or os.environ.get("FF_MODE", "full")
        self.profiles = ProfileStore(self.db)
        self._workers: dict[str, threading.Thread] = {}
        self._deploy_events: dict[str, dict] = {}

    # --- request lifecycle -------------------------------------------------

    def submit(self, body: dict) -> dict:
        deploy_event = body.get("deploy_event") or {}
        row = self.db.create_request(
            body["episode_id"], body["service"], deploy_event,
            float(body.get("deadline_s", 240)), body.get("budget") or {})
        self._deploy_events[row["request_id"]] = deploy_event
        t = threading.Thread(target=self._worker, args=(row["request_id"],),
                             daemon=True)
        self._workers[row["request_id"]] = t
        t.start()
        return {"request_id": row["request_id"], "state": row["state"]}

    def wait(self, request_id: str, timeout: float = 60) -> None:
        t = self._workers.get(request_id)
        if t is not None:
            t.join(timeout)

    def _worker(self, request_id: str) -> None:
        try:
            self._run(request_id)
        except Exception as exc:
            results.degrade(self.db, request_id, f"{type(exc).__name__}: {exc}")

    def _probe_spec(self, service: str, revision: str) -> dict:
        resp = httpx.get(f"{self.world_api}/world/probe-spec",
                         params={"service": service, "revision": revision},
                         timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _revisions(self, request_id: str, service: str) -> tuple[str, str]:
        ev = self._deploy_events.get(request_id, {})
        to_rev = ev.get("to_revision", "")
        from_rev = ev.get("from_revision", "")
        if not to_rev:
            resp = httpx.get(f"{self.world_api}/world/services", timeout=10)
            resp.raise_for_status()
            to_rev = resp.json().get(service, {}).get("revision", "candidate")
        # Any non-current revision string maps to the clean spec.
        return to_rev, from_rev or f"{service}-baseline"

    def _run(self, request_id: str) -> None:
        row = self.db.get_request(request_id)
        service = row["service"]
        manifest = json.loads(row["manifest_json"])
        caps = inventory.capabilities()
        for h in compiler.compile(manifest, caps):
            self.db.insert_hazard(request_id, h)
        self.db.set_state(request_id, "COMPILED")
        hazards = self.db.hazards_for(request_id)  # floor + early proposals
        budget = json.loads(row["budget_json"] or "{}")
        deadline_epoch = _epoch(row["deadline_at"])
        p = planner.plan(hazards, budget, row["deadline_s"], caps,
                         self.profiles, self.mode)
        base_seed = derive_seed(row["manifest_digest"])

        if not hazards:
            self.db.set_state(request_id, "ANALYZING")  # no-hazard fast path
            results.finalize(self.db, self.db.get_request(request_id), [], [],
                             {"probe_seconds": 0.0, "steps": 0},
                             plan_digest=p["plan_digest"], mode=self.mode,
                             seed=base_seed)
            return

        step_ids = [self.db.insert_plan_step(request_id, s) for s in p["steps"]]
        self.db.set_state(request_id, "PLANNED")
        self.db.set_state(request_id, "RUNNING")

        by_hazard = {h["hazard_id"]: h for h in hazards}
        max_probe_s = budget.get("max_probe_seconds")
        max_probe_s = float(max_probe_s) if max_probe_s is not None else float("inf")
        signal_results: dict[str, dict] = {}
        dispo: dict[str, dict] = {}
        fidelity_reports: list[dict] = []
        counterexamples: list[dict] = []
        probe_spent, steps_run, stop_all = 0.0, 0, False

        for step_id, s in zip(step_ids, p["steps"]):
            hid = s["hazard_id"]
            h = by_hazard[hid]
            if stop_all:
                self.db.update_step(step_id, {"state": "skipped"})
                continue
            if deadline_epoch is not None and time.time() > deadline_epoch:
                self.db.update_step(step_id, {"state": "skipped"})
                if hid not in dispo:
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": "inconclusive_budget",
                                  "mode": s["mode"]}
                continue
            if s["run_if"] == planner.RUN_IF_SIGNAL_INCONCLUSIVE:
                sig = signal_results.get(hid)
                if sig is not None and sig["disposition"] != "inconclusive_signal":
                    self.db.update_step(step_id, {"state": "skipped"})
                    continue
            self.db.update_step(step_id, {"state": "running",
                                          "started_at": now_iso()})
            if s["mode"] == "signal":
                res = signals.run_signal(
                    s, h, service, self.profiles, deadline_epoch,
                    base=self.observe_api,
                    deployed_at=self._deploy_events.get(request_id, {}).get("at"))
                signal_results[hid] = res
                self.db.update_step(step_id, {"state": "done", "result": res,
                                              "ended_at": now_iso()})
                if res["disposition"] in ("projected_boundary",
                                          "bounded_within_envelope"):
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": res["disposition"],
                                  "mode": "signal"}
            else:
                seed = derive_seed(row["manifest_digest"], hid)
                to_rev, from_rev = self._revisions(request_id, service)
                cand = self._probe_spec(service, to_rev)
                clean = self._probe_spec(service, from_rev)
                ctx = ProbeContext(
                    target=self.probe_api, service=service, revision=to_rev,
                    seed=seed, spec=cand["spec"],
                    spec_digest=cand["spec_digest"], request=row, hazard=h,
                    previous_revision=from_rev, clean_spec=clean["spec"],
                    clean_spec_digest=clean["spec_digest"],
                    profiles=self.profiles,
                    budget_s=max(0.0, max_probe_s - probe_spent),
                    deadline_at=deadline_epoch)
                runner = playbooks.get(s["template"])
                if runner is None:
                    self.db.update_step(step_id, {"state": "done",
                                                  "result": {"error": "no playbook"},
                                                  "ended_at": now_iso()})
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": "unsupported", "mode": "probe"}
                    continue
                started_at, t0 = now_iso(), time.time()
                res = runner(ctx)
                probe_spent += time.time() - t0
                step_result = {k: v for k, v in res.items()
                               if k not in ("counterexample", "action_log")}
                self.db.update_step(step_id, {"state": "done",
                                              "result": step_result,
                                              "ended_at": now_iso()})
                self.db.insert_probe_run(step_id, {
                    "instance_id": None, "seed": seed,
                    "measurements": res.get("measurements", {}),
                    "side_effects": [{"side_effect_attempts":
                                      res.get("measurements", {})
                                      .get("side_effect_attempts"),
                                      "contained": True}],
                    "stop_reason": res.get("stop_reason"),
                    "started_at": started_at, "ended_at": now_iso()})
                if res.get("fidelity_report"):
                    fidelity_reports.append(res["fidelity_report"])
                d = res["disposition"]
                if d == "counterexample":
                    cx = res["counterexample"]
                    self.db.insert_counterexample(request_id, cx)
                    try:
                        verified, observed = counterexample.replay(
                            cx, self.probe_api)
                    except Exception:
                        verified, observed = False, {}
                    if verified:
                        self.db.mark_replay_verified(
                            cx["cx_id"], observed.get("first_divergence_age"))
                        cx["replay_verified"] = True
                    counterexamples.append(cx)
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": "counterexample",
                                  "mode": "probe"}
                    if h.get("impact") == "high":
                        stop_all = True  # plan stop_all_if
                elif d == "within_envelope":
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": "within_envelope",
                                  "mode": "probe"}
                elif res.get("stop_reason") == "inconclusive_budget":
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": "inconclusive_budget",
                                  "mode": "probe"}
                else:
                    dispo[hid] = {"hazard_id": hid, "class": h["class"],
                                  "disposition": "unsupported", "mode": "probe"}
            steps_run += 1

        # Hazards still undecided: planner drops, unescalatable signals, or
        # steps skipped behind a stop_all — none of them may look clean.
        unresolved_by = {}
        for u in p["unresolved"]:
            unresolved_by.setdefault(u["hazard_id"], u)
        for h in hazards:
            hid = h["hazard_id"]
            if hid in dispo:
                continue
            sig = signal_results.get(hid)
            u = unresolved_by.get(hid)
            if u is not None and (sig is None
                                  or sig["disposition"] == "inconclusive_signal"):
                d, mode = u["disposition"], None
            elif stop_all:
                d, mode = "inconclusive", None
            else:
                d, mode = "unsupported", "signal" if sig is not None else None
            dispo[hid] = {"hazard_id": hid, "class": h["class"],
                          "disposition": d, "mode": mode}

        self.db.set_state(request_id, "ANALYZING")
        profile_ids = [r["profile_id"] for r in self.db.query(
            "SELECT profile_id FROM stable_profiles WHERE service=? "
            "ORDER BY profile_id", (service,))]
        results.finalize(
            self.db, self.db.get_request(request_id), list(dispo.values()),
            fidelity_reports,
            {"probe_seconds": round(probe_spent, 3), "steps": steps_run},
            plan_digest=p["plan_digest"], mode=self.mode, seed=base_seed,
            profile_ids=profile_ids, counterexamples=counterexamples)

    # --- read side ---------------------------------------------------------

    def packet(self, request_id: str) -> dict | None:
        row = self.db.get_request(request_id)
        if row is None:
            return None
        cx_rows = self.db.query(
            "SELECT cx_id FROM counterexamples WHERE request_id=? ORDER BY cx_id",
            (request_id,))
        envs = self.db.query(
            "SELECT envelope_json FROM ff_envelopes WHERE request_id=? "
            "ORDER BY minted_at, observation_id", (request_id,))
        return {
            "request_id": row["request_id"], "episode_id": row["episode_id"],
            "service": row["service"], "state": row["state"],
            "outcome": row["outcome"],
            "manifest": json.loads(row["manifest_json"]),
            "manifest_digest": row["manifest_digest"],
            "deadline_at": row["deadline_at"],
            "budget": json.loads(row["budget_json"] or "{}"),
            "hazards": self.db.hazards_for(request_id),
            "plan": self.db.steps_for(request_id),
            "snapshot": json.loads(row["snapshot_json"] or "null"),
            "envelopes": [json.loads(e["envelope_json"]) for e in envs],
            "counterexamples": [self.db.get_counterexample(r["cx_id"])
                                for r in cx_rows],
            "created_at": row["created_at"], "decided_at": row["decided_at"],
        }

    def resolve_request(self, episode_or_service: str) -> str | None:
        """Newest request by episode_id, else by service name."""
        for col in ("episode_id", "service"):
            row = self.db.one(
                f"SELECT request_id FROM ff_requests WHERE {col}=? "
                "ORDER BY created_at DESC, request_id DESC LIMIT 1",
                (episode_or_service,))
            if row:
                return row["request_id"]
        return None

    # --- operations --------------------------------------------------------

    def propose(self, request_id: str, proposals: list[dict]) -> dict:
        row = self.db.get_request(request_id)
        if row is None:
            raise ValueError(f"unknown request {request_id}")
        if row["state"] in TERMINAL:
            raise ValueError(f"request {request_id} is terminal")
        merged, rejected = compiler.merge_proposals(
            self.db.hazards_for(request_id), proposals)
        for h in merged:
            self.db.insert_hazard(request_id, h)
        return {"merged": sorted(h["hazard_id"] for h in merged),
                "rejected": rejected}

    def replay_cx(self, cx_id: str, target=None) -> dict:
        cx = self.db.get_counterexample(cx_id)
        if cx is None:
            raise ValueError(f"unknown counterexample {cx_id}")
        verified, observed = counterexample.replay(cx, target or self.probe_api)
        if verified:
            self.db.mark_replay_verified(cx_id,
                                         observed.get("first_divergence_age"))
        return {"verified": verified,
                "first_divergence_age": observed.get("first_divergence_age")}

    def seed_profiles(self, service: str, target=None, clean: dict | None = None) -> dict:
        """Baseline the KNOWN-GOOD behavior: clean-revision probe runs derive
        the stable probe profiles, and flat telemetry stats seed the signal
        envelopes. Idempotent enough: newest profile wins at read time."""
        target = target or self.probe_api
        if clean is None:
            clean = self._probe_spec(service, f"{service}-profile-baseline")
        fp = env_fingerprint({"spec_digest": clean["spec_digest"]})
        seed = derive_seed(f"profile|{service}")
        out = []

        s = ProbeSession(target)
        try:
            s.create(service, "profile-baseline", seed, clean["spec"])
            s.cycle(100)
            prev = s.counters()["open_handles"]
            deltas = []
            for _ in range(4):
                s.cycle(100)
                cur = s.counters()["open_handles"]
                deltas.append((cur - prev) / 100.0)
                prev = cur
        finally:
            s.destroy()
        stats = {"slope_per_cycle": {"median": playbooks.median(deltas),
                                     "mad": mad(deltas), "n": len(deltas)}}
        out.append({"template": "resource_lifecycle_v1",
                    "profile_id": self.profiles.put(
                        service, "resource_lifecycle_v1", fp, stats)})

        s = ProbeSession(target)
        try:
            s.create(service, "profile-baseline", seed, clean["spec"])
            s.dependency(0.2, 0)
            prev = s.counters()["queue_depth"]
            deltas = []
            for _ in range(4):
                s.requests(100, 8)
                cur = s.counters()["queue_depth"]
                deltas.append(float(cur - prev))
                prev = cur
        finally:
            s.destroy()
        stats = {"queue_delta_per_round": {"median": playbooks.median(deltas),
                                           "mad": mad(deltas), "n": len(deltas)}}
        out.append({"template": "rate_balance_v1",
                    "profile_id": self.profiles.put(
                        service, "rate_balance_v1", fp, stats)})

        sig_stats = {"slope": {"median": 0.0, "mad": 0.05, "n": 11}}
        for tmpl in ("growth_projection", "queue_drift_projection"):
            out.append({"template": tmpl,
                        "profile_id": self.profiles.put(
                            service, tmpl, signals.SIGNAL_FP, sig_stats)})
        return {"profiles": out}

    # --- test-only ---------------------------------------------------------

    def load_fixtures(self, body: dict) -> dict:
        """Pre-armed terminal request packets. Envelopes are RE-MINTED from
        payload templates at load time — a fixture with a frozen signature
        would be stale against the live OBS_SIGNING_KEY."""
        loaded = {"requests": 0, "envelopes": 0}
        for r in body.get("requests", []):
            rid, eid = r["request_id"], r["episode_id"]
            if r["state"] not in STATES:
                raise ValueError(f"unknown state {r['state']!r}")
            for sql in (
                "DELETE FROM probe_runs WHERE step_id IN "
                "(SELECT step_id FROM plan_steps WHERE request_id=?)",
                "DELETE FROM plan_steps WHERE request_id=?",
                "DELETE FROM hazards WHERE request_id=?",
                "DELETE FROM counterexamples WHERE request_id=?",
                "DELETE FROM ff_envelopes WHERE request_id=?",
                "DELETE FROM ff_requests WHERE request_id=?",
            ):
                self.db.execute(sql, (rid,))
            from .manifest import canonicalize, digest
            m = r.get("manifest") or {"items": []}
            self.db.execute(
                """INSERT INTO ff_requests(request_id,episode_id,service,
                   manifest_json,manifest_digest,deadline_at,deadline_s,
                   budget_json,state,outcome,snapshot_json,created_at,decided_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, eid, r["service"], json.dumps(canonicalize(m)), digest(m),
                 r.get("deadline_at"), r.get("deadline_s", 240),
                 json.dumps(r.get("budget", {})), r["state"], r.get("outcome"),
                 json.dumps(r.get("snapshot")) if r.get("snapshot") else None,
                 now_iso(),
                 now_iso() if r["state"] in TERMINAL else None))
            for h in r.get("hazards", []):
                self.db.insert_hazard(rid, h)
            for cx in r.get("counterexamples", []):
                self.db.insert_counterexample(rid, cx)
            for spec in r.get("envelopes", []):
                env = envelope.mint(
                    spec["type"], spec["scope"], spec["payload"],
                    spec.get("quality"),
                    ttl_seconds=int(spec.get("ttl_seconds", 604800)))
                self.db.insert_envelope(rid, eid, env)
                loaded["envelopes"] += 1
            loaded["requests"] += 1
        return loaded

    def reset(self) -> None:
        self.db._conn.close()  # noqa: SLF001 — test-only endpoint
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Db(self.db_path)
        self.profiles = ProfileStore(self.db)
        self._workers.clear()
        self._deploy_events.clear()


# --- MCP face ----------------------------------------------------------------


def build_mcp(ff: FastForward, port: int):
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("rollout-fastforward", host="127.0.0.1", port=port)

    @mcp.tool()
    def get_hazard_report(episode_or_service: str) -> str:
        """Compiled temporal hazards for the newest Fast-Forward request on
        this episode (or service name): class, matched change traits,
        expected symptom, planned experiments, and current status. Hazards
        are a deterministic floor from the change manifest — they cannot be
        argued away, only investigated."""
        rid = ff.resolve_request(episode_or_service)
        if rid is None:
            return json.dumps({"error": f"no request for {episode_or_service!r}"})
        pkt = ff.packet(rid)
        return json.dumps({"request_id": rid, "episode_id": pkt["episode_id"],
                           "service": pkt["service"], "state": pkt["state"],
                           "hazards": pkt["hazards"], "plan": pkt["plan"]})

    @mcp.tool()
    def get_fastforward_result(episode_or_service: str) -> str:
        """The full Fast-Forward result packet for the newest request on
        this episode (or service name), INCLUDING the signed
        fastforward_result / temporal_counterexample envelopes verbatim —
        hand those to rollout-intel unmodified. Outcomes
        inconclusive_budget and unsupported_temporal_risk are never a pass."""
        rid = ff.resolve_request(episode_or_service)
        if rid is None:
            return json.dumps({"error": f"no request for {episode_or_service!r}"})
        return json.dumps(ff.packet(rid))

    @mcp.tool()
    def get_counterexample(cx_id: str) -> str:
        """One temporal counterexample artifact: the minimal replayable
        event sequence, expected stable behavior, observed candidate
        divergence, and first_divergence_age. replay_verified means the
        sequence was re-driven and diverged identically."""
        cx = ff.db.get_counterexample(cx_id)
        if cx is None:
            return json.dumps({"error": f"unknown counterexample {cx_id!r}"})
        return json.dumps(cx)

    return mcp


# --- REST face ---------------------------------------------------------------


def build_rest(ff: FastForward, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            parse_qs(parsed.query)
            parts = [p for p in parsed.path.split("/") if p]
            if parsed.path == "/ff/health":
                self._send(200, {"ok": True})
            elif len(parts) == 3 and parts[:2] == ["ff", "requests"]:
                pkt = ff.packet(parts[2])
                if pkt is None:
                    self._send(404, {"error": f"unknown request {parts[2]}"})
                else:
                    self._send(200, pkt)
            elif (len(parts) == 4 and parts[:2] == ["ff", "episodes"]
                    and parts[3] == "result-envelopes"):
                self._send(200, {"envelopes":
                                 ff.db.envelopes_for_episode(parts[2])})
            else:
                self._send(404, {"error": f"unknown GET {parsed.path}"})

        def do_POST(self):  # noqa: N802
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            try:
                body = self._body()
                if parsed.path == "/ff/requests":
                    self._send(200, ff.submit(body))
                elif (len(parts) == 4 and parts[:2] == ["ff", "requests"]
                        and parts[3] == "proposals"):
                    self._send(200, ff.propose(parts[2],
                                               body.get("hazards", [])))
                elif (len(parts) == 4 and parts[:2] == ["ff", "counterexamples"]
                        and parts[3] == "replay"):
                    self._send(200, ff.replay_cx(parts[2]))
                elif parsed.path == "/ff/profiles/seed":
                    self._send(200, ff.seed_profiles(body["service"]))
                elif parsed.path == "/ff/fixtures/load":
                    self._send(200, ff.load_fixtures(body))
                elif parsed.path == "/ff/replay/reset":
                    ff.reset()
                    self._send(200, {"reset": True})
                else:
                    self._send(404, {"error": f"unknown POST {parsed.path}"})
            except (KeyError, ValueError) as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:  # upstream (world/probe) failures
                self._send(502, {"error": str(exc)})

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-port", type=int, default=7630)
    ap.add_argument("--rest-port", type=int, default=7631)
    args = ap.parse_args()

    ff = FastForward(os.environ.get("FF_DB", "ff.db"))
    rest = build_rest(ff, args.rest_port)
    threading.Thread(target=rest.serve_forever, daemon=True).start()
    print(f"rollout-fastforward: mcp=:{args.mcp_port} rest=:{args.rest_port} "
          f"mode={ff.mode} world={ff.world_api} probe={ff.probe_api}")
    build_mcp(ff, args.mcp_port).run(transport="streamable-http")


if __name__ == "__main__":
    main()
