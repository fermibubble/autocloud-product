"""rollout-intel: the Rollout Intelligence Layer service.

Two faces, one SQLite state (the product's world.py pattern):
  - MCP (:7610) — what the reviewer agent calls: get_context_pack,
    evaluate_policy, record_checkpoint (+ dossier/retrieval tools in later
    phases).
  - REST (:7611) — what the relay, collectors, scripts, and humans call:
    episode/checkpoint lifecycle, outcomes, feedback, metrics, fixtures.

Server-side invariant (the deterministic layer the LLM cannot override):
record_checkpoint re-runs the policy evaluator over the submitted envelopes;
an agent verdict of "healthy" against a policy fail/insufficient result is
rejected with policy_conflict rather than stored as truth.

Run: INTEL_DB=intel.db uv run --project . python -m rollout_intel.service \
       --mcp-port 7610 --rest-port 7611 \
       --policy ../policies/rollout-slo.yaml --catalog ../catalog/services.yaml
"""

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mcp.server.fastmcp import FastMCP

from . import envelope, fingerprint, identity, learning, retrieval
from .db import STAGE_LADDER, Db, now_iso
from .dossier import DossierStore, MemoryProjector
from .policy import PolicyPack, evaluate

# Stage -> minutes until the next check (sim time is scaled by the relay).
NEXT_CHECK_MINUTES = {"T+0": 5, "T+5": 10, "T+15": 15, "T+30": None}

VALID_VERDICTS = ("healthy", "regression-suspected", "insufficient-evidence")


def _summarize_payload(env: dict) -> str:
    payload = env.get("payload", {})
    if env.get("type") == "metric_window":
        for s in payload.get("series", []):
            if s.get("points"):
                return f"{payload.get('metric_type')} latest={s['points'][-1].get('value')}"
        return f"{payload.get('metric_type')} (empty)"
    if env.get("type") == "log_scan":
        entries = payload.get("entries", [])
        errors = [e for e in entries if e.get("severity") in ("ERROR", "CRITICAL")]
        return f"{len(entries)} entries, {len(errors)} error+"
    if env.get("type") == "workload_state":
        return f"{len(payload.get('services', []))} services"
    return env.get("type", "observation")


class Intel:
    def __init__(self, db_path: str, policy_path: str, catalog_path: str):
        self.db = Db(db_path)
        self.policy_path = policy_path
        self.pack = PolicyPack(policy_path)
        self.catalog_path = catalog_path
        # Per-(episode, stage) envelopes collected by run_stage_checks; lets
        # record_checkpoint reuse verified evidence without the agent
        # re-threading envelope JSON (static scripts cannot).
        self._stage_cache: dict[tuple[str, str], list[dict]] = {}
        identity.load_catalog(self.db, catalog_path)
        projector = MemoryProjector() if os.environ.get("ENSEMBLE_TOKEN") else None
        self.dossiers = DossierStore(self.db, projector)

    # --- REST-side operations ---------------------------------------------

    def create_episode(self, deploy_event: dict) -> dict:
        service = identity.resolve(self.db, deploy_event)
        fp = fingerprint.from_deploy_event(deploy_event, service)
        # The event's architecture signal (not the stale service row) is
        # what detects a change; sensitive dossier claims expire and the
        # row learns the new version before the episode consults anything.
        new_arch = fp.get("architecture_version", "")
        stored_arch = service.get("architecture_version") or ""
        if new_arch and stored_arch and new_arch != stored_arch:
            self.dossiers.invalidate_architecture(service["service_uid"], new_arch)
            self.db.execute(
                "UPDATE services SET architecture_version=? WHERE service_uid=?",
                (new_arch, service["service_uid"]))
            service["architecture_version"] = new_arch
        self.dossiers.sweep_expired()
        episode = self.db.create_episode(service["service_uid"], fp, deploy_event)
        episode["identity_status"] = service["status"]
        return episode

    def open_checkpoint(self, episode_id: str, stage: str, session_id: str) -> dict:
        if not self.db.one("SELECT 1 FROM episodes WHERE episode_id=?", (episode_id,)):
            raise ValueError(f"unknown episode {episode_id}")
        if stage not in STAGE_LADDER:
            raise ValueError(f"unknown stage {stage}")
        return self.db.open_checkpoint(episode_id, stage, session_id, now_iso())

    def decision_quality(self) -> dict:
        rows = self.db.query(
            """SELECT final_verdict, final_label, COUNT(*) AS n FROM episodes
               WHERE final_label IS NOT NULL GROUP BY final_verdict, final_label"""
        )
        false_safe = sum(r["n"] for r in rows
                         if r["final_verdict"] == "healthy"
                         and r["final_label"] in ("regressed", "rolled_back"))
        false_halt = sum(r["n"] for r in rows
                         if r["final_verdict"] == "regression-suspected"
                         and r["final_label"] == "healthy")
        total = sum(r["n"] for r in rows)
        return {"labeledEpisodes": total, "falseSafe": false_safe,
                "falseHalt": false_halt, "cells": rows}

    # --- shared by MCP tools ------------------------------------------------

    def open_checkpoint_for(self, episode_id: str, stage: str) -> dict | None:
        return self.db.one(
            """SELECT * FROM checkpoints WHERE episode_id=? AND stage=?
               AND completed_at IS NULL""", (episode_id, stage))

    def resolve_episode(self, episode_or_service: str, stage: str) -> str | None:
        """Accepts an episode id directly, or a service NAME — resolved to
        the unique episode with an open checkpoint at this stage. The
        service-name path is what makes deterministic scripted reviewers
        possible (scripts can't echo per-run ids); ambiguity errors loudly
        for LIVE episodes. Fixture episodes (fx_ prefix, test-only) resolve
        oldest-checkpoint-first instead, so a two-arm experiment can drain
        one pre-armed checkpoint per eval session deterministically."""
        if episode_or_service.startswith(("ep_", "fx_")):
            return episode_or_service
        rows = self.db.query(
            """SELECT c.episode_id FROM checkpoints c
               JOIN episodes e ON e.episode_id = c.episode_id
               JOIN services s ON s.service_uid = e.service_uid
               WHERE s.name=? AND c.stage=? AND c.completed_at IS NULL
               ORDER BY c.created_at, c.episode_id""",
            (episode_or_service, stage))
        # A live rollout always outranks armed fixtures: leftover eval
        # checkpoints must never absorb (or block) a real episode's record.
        live = [r for r in rows if not r["episode_id"].startswith("fx_")]
        if live:
            return live[0]["episode_id"] if len(live) == 1 else None
        # Fixture-only: drain deterministically, oldest episode id first
        # (created_at has 1s resolution; ids break the tie stably).
        return rows[0]["episode_id"] if rows else None

    def _min_full_coverage_offset(self) -> int:
        """The earliest ladder offset by which EVERY policy rule has had at
        least one stage to run — the floor below which no stabilization
        window may end the ladder."""
        offsets = {"T+0": 0, "T+5": 5, "T+15": 15, "T+30": 30}
        floor = 0
        for rule in self.pack.rules:
            stages = rule.get("stages") or []
            if stages:
                floor = max(floor, min(offsets.get(s, 0) for s in stages))
        return floor

    def resolve_service_uid(self, service: str) -> str | None:
        """Accepts a canonical svc:// uid or a bare service name."""
        if service.startswith("svc://"):
            row = self.db.one("SELECT service_uid FROM services WHERE service_uid=?",
                              (service,))
        else:
            row = self.db.one("SELECT service_uid FROM services WHERE name=?", (service,))
        return row["service_uid"] if row else None

    def run_stage_checks(self, episode_or_service: str, stage: str) -> dict:
        """Server-side standard evidence collection: fetch the stage bundle
        from gcp-observe (which alone mints/signs envelopes), verify and
        store every observation against the open checkpoint, and evaluate
        policy. Returns the policy result plus envelope summaries — the
        agent reasons over these and then calls record_checkpoint."""
        episode_id = self.resolve_episode(episode_or_service, stage)
        if episode_id is None:
            return {"error": f"no open {stage} checkpoint resolvable from "
                             f"{episode_or_service!r}"}
        checkpoint = self.open_checkpoint_for(episode_id, stage)
        if checkpoint is None:
            return {"error": f"no open checkpoint for {episode_id} at {stage}"}
        episode = self.db.one("SELECT * FROM episodes WHERE episode_id=?", (episode_id,))
        service = self.db.one("SELECT * FROM services WHERE service_uid=?",
                              (episode["service_uid"],))
        import httpx  # local import: REST face must not require it at startup

        observe_api = os.environ.get("OBSERVE_API", "http://127.0.0.1:7601")
        try:
            resp = httpx.get(f"{observe_api}/observe/bundle",
                             params={"service": service["name"], "stage": stage}, timeout=60)
            resp.raise_for_status()
            envs = resp.json()
        except Exception as exc:
            return {"error": f"evidence collection failed: {exc}"}
        ff_api = os.environ.get("FF_API")
        if ff_api:
            # On ANY failure proceed without FF envelopes — the v2
            # temporal-evidence rule then reports insufficient, never pass.
            try:
                ff_resp = httpx.get(
                    f"{ff_api}/ff/episodes/{episode_id}/result-envelopes", timeout=5)
                envs.extend(ff_resp.json().get("envelopes", []))
            except Exception:
                pass
        for env in envs:
            ok, _ = envelope.verify(env)
            self.db.insert_observation(episode_id, checkpoint["checkpoint_id"], env, ok)
        result = evaluate(self.pack, stage, envs)
        result["episode_id"] = episode_id
        result["observations"] = [
            {"observation_id": e.get("observation_id"), "type": e.get("type"),
             "quality": e.get("quality"),
             "summary": _summarize_payload(e)}
            for e in envs
        ]
        self._stage_cache[(episode_id, stage)] = envs
        return result

    def context_pack(self, episode_id: str, as_of: str | None = None) -> dict:
        episode = self.db.one("SELECT * FROM episodes WHERE episode_id=?", (episode_id,))
        if not episode:
            return {"error": f"unknown episode {episode_id}"}
        service = self.db.one("SELECT * FROM services WHERE service_uid=?",
                              (episode["service_uid"],))
        prior = self.db.query(
            """SELECT stage, stage_verdict, policy_status, report_version, completed_at
               FROM checkpoints WHERE episode_id=? AND completed_at IS NOT NULL
               ORDER BY completed_at""", (episode_id,))
        pack = {
            "episode": {
                "episode_id": episode_id,
                "service_uid": episode["service_uid"],
                "revision_from": episode["revision_from"],
                "revision_to": episode["revision_to"],
                "fingerprint": json.loads(episode["fingerprint_json"]),
                "status": episode["status"],
            },
            "identity": {
                "status": service["status"], "source": service["source"],
                "owner": service["owner"],
                "note": ("identity is an INFERRED CANDIDATE — treat scope as unconfirmed"
                         if service["status"] == "candidate" else "confirmed via catalog"),
            },
            "policy": {"version": self.pack.version,
                       "hard_rules_summary": self.pack.summary()},
            "prior_checkpoints": prior,
            "generated_at": now_iso(),
        }
        dossier = self.dossiers.get(episode["service_uid"], as_of)
        pack["dossier"] = {
            "claims": dossier["claims"],
            "note": ("Dossier claims INFORM interpretation; they never satisfy "
                     "a policy rule and never substitute for live evidence. "
                     "hypothesized/asserted claims are unverified."),
        }
        pack["precedents"] = retrieval.find_precedents(
            self.db, service, json.loads(episode["fingerprint_json"]),
            as_of=as_of, exclude_episode=episode_id, episode_id=episode_id,
            tool="get_context_pack")
        self.db.audit_retrieval(episode_id, "get_context_pack",
                                {"as_of": as_of},
                                [c["rev_id"] for c in dossier["claims"]], as_of)
        return pack

    def record(self, episode_or_service: str, stage: str, envelopes: list[dict],
               stage_verdict: str, reasoning_summary: str, report_md: str,
               precedent_ids: list[str], dossier_fields: list[str]) -> dict:
        episode_id = self.resolve_episode(episode_or_service, stage)
        if episode_id is None:
            return {"error": f"no open {stage} checkpoint resolvable from "
                             f"{episode_or_service!r}"}
        checkpoint = self.open_checkpoint_for(episode_id, stage)
        if checkpoint is None:
            return {"error": f"no open checkpoint for episode {episode_id} stage {stage} "
                             "(wrong episode_id, wrong stage, or already recorded)"}
        if stage_verdict not in VALID_VERDICTS:
            return {"error": f"stage_verdict must be one of {VALID_VERDICTS}"}

        # No envelopes supplied -> use the verified set run_stage_checks
        # collected for this checkpoint (the scripted-reviewer path; also
        # the common real-model path after calling run_stage_checks).
        if not envelopes:
            envelopes = self._stage_cache.get((episode_id, stage), [])

        # Evidence transplant guard: a validly SIGNED envelope for a
        # different service must not satisfy this episode's policy —
        # signatures prove provenance, scope proves relevance. Rejected
        # loudly rather than silently filtered, so the caller learns.
        service_name = self.db.one(
            "SELECT s.name FROM services s JOIN episodes e "
            "ON e.service_uid = s.service_uid WHERE e.episode_id=?",
            (episode_id,))["name"]
        foreign = [e.get("observation_id") for e in envelopes
                   if e.get("scope", {}).get("service")
                   and e["scope"]["service"] != service_name]
        if foreign:
            return {"error": (f"scope_mismatch: observations {foreign} are for a "
                              f"different service than this episode "
                              f"({service_name}); submit evidence for the "
                              "service under review")}
        verdict_result = evaluate(self.pack, stage, envelopes)
        for env in envelopes:
            ok, _ = envelope.verify(env)
            self.db.insert_observation(episode_id, checkpoint["checkpoint_id"], env, ok)

        policy_status = verdict_result["policy_status"]
        conflict = (
            (stage_verdict == "healthy" and policy_status in ("fail", "insufficient_evidence"))
            or (stage_verdict == "insufficient-evidence" and policy_status == "fail")
        )
        if conflict:
            # Stored for audit, rejected for effect: the deterministic layer wins.
            self.db.insert_decision(checkpoint["checkpoint_id"], "stage_verdict",
                                    {"rejected_verdict": stage_verdict,
                                     "policy_status": policy_status},
                                    {"reason": "policy_conflict"})
            return {"error": (f"policy_conflict: policy evaluated {policy_status} "
                              f"({verdict_result['required_missing'] or 'rule failures'}) — "
                              f"a {stage_verdict!r} verdict cannot be recorded. Reconcile "
                              "your verdict with the policy result."),
                    "policy": verdict_result}

        # Dynamic scheduling (research phase 5): a GOVERNED stabilization
        # window (approved/observed dossier claim only — governed_value
        # refuses asserted/hypothesized) ends the ladder once this stage's
        # offset reaches it — but never before every policy rule has had a
        # stage to run at: a window of 5 must not skip the T+15-only
        # fatal-log rule, and booleans/zero/negative values are not windows.
        stage_offset = {"T+0": 0, "T+5": 5, "T+15": 15, "T+30": 30}[stage]
        window = self.dossiers.governed_value(
            self.db.one("SELECT service_uid FROM episodes WHERE episode_id=?",
                        (episode_id,))["service_uid"],
            "stabilization_window_minutes")
        next_minutes = NEXT_CHECK_MINUTES.get(stage)
        if (isinstance(window, (int, float)) and not isinstance(window, bool)
                and window > 0):
            effective = max(window, self._min_full_coverage_offset())
            if stage_offset >= effective:
                next_minutes = None
        next_check_at = f"+{next_minutes}m" if next_minutes else None
        completed = self.db.complete_checkpoint(
            checkpoint["checkpoint_id"], stage_verdict, policy_status,
            verdict_result["policy_version"], False, report_md, next_check_at)
        if completed is None:
            return {"error": (f"conflict: checkpoint {checkpoint['checkpoint_id']} "
                              "was recorded concurrently; this attempt changed "
                              "nothing")}
        self.db.insert_decision(
            checkpoint["checkpoint_id"], "stage_verdict",
            {"stage_verdict": stage_verdict, "policy_status": policy_status,
             "reasoning_summary": reasoning_summary[:2000]},
            {"observation_ids": [e.get("observation_id") for e in envelopes],
             "policy_rule_ids": [r["rule_id"] for r in verdict_result["rule_results"]],
             "precedent_episode_ids": precedent_ids,
             "dossier_fields_used": dossier_fields})
        return {"checkpoint_id": checkpoint["checkpoint_id"],
                "policy_status": policy_status,
                "report_version": completed["report_version"],
                "next_check_at": next_check_at,
                "policy": verdict_result}


# --- MCP face ----------------------------------------------------------------


def build_mcp(intel: Intel, port: int) -> FastMCP:
    mcp = FastMCP("rollout-intel", host="127.0.0.1", port=port)

    @mcp.tool()
    def get_context_pack(episode_id: str, stage: str = "") -> str:
        """Everything known about this rollout episode before you
        investigate: identity (and whether it is confirmed or merely
        inferred), the hard policy rules, and prior checkpoint verdicts.
        Accepts an episode id, or a service NAME plus stage (resolved to
        the open checkpoint). Call this FIRST at every checkpoint."""
        resolved = intel.resolve_episode(episode_id, stage) if stage else episode_id
        if resolved is None:
            return json.dumps({"error": f"no open {stage} checkpoint for {episode_id!r}"})
        return json.dumps(intel.context_pack(resolved))

    @mcp.tool()
    def run_stage_checks(episode_or_service: str, stage: str) -> str:
        """Collect the standard evidence bundle for this stage (server-side,
        from gcp-observe — signed at the source), store it against the open
        checkpoint, and evaluate the deterministic policy. Returns the
        policy result (pass | fail | insufficient_evidence), per-rule
        details, and observation summaries. Accepts an episode id or the
        service NAME (resolved to its open checkpoint). Call this first at
        every stage, then reason, then record_checkpoint."""
        return json.dumps(intel.run_stage_checks(episode_or_service, stage))

    @mcp.tool()
    def evaluate_policy(stage: str, observations: str) -> str:
        """Deterministic policy evaluation over SIGNED observation envelopes
        you supply explicitly (JSON array of envelope objects, verbatim from
        gcp-observe tools). Use run_stage_checks for the standard bundle;
        this is for evaluating extra evidence you gathered yourself."""
        try:
            envs = json.loads(observations)
            assert isinstance(envs, list)
        except Exception:
            return json.dumps({"error": "observations must be a JSON array of envelopes"})
        return json.dumps(evaluate(intel.pack, stage, envs))

    @mcp.tool()
    def record_checkpoint(episode_or_service: str, stage: str,
                          stage_verdict: str, reasoning_summary: str,
                          report_md: str, observations: str = "[]",
                          precedent_episode_ids: str = "[]",
                          dossier_fields_used: str = "[]") -> str:
        """Record this stage's verdict and report into the immutable
        episode. Evidence: the envelopes run_stage_checks already collected
        for this checkpoint (default), plus any extra you pass in
        observations. The policy is re-evaluated server-side: a healthy
        verdict that contradicts the policy result is REJECTED
        (policy_conflict) — reconcile and re-record. Verdict vocabulary:
        healthy | regression-suspected | insufficient-evidence."""
        try:
            envs = json.loads(observations)
            precedents = json.loads(precedent_episode_ids)
            fields = json.loads(dossier_fields_used)
        except Exception:
            return json.dumps({"error": "observations/precedents/fields must be JSON arrays"})
        return json.dumps(intel.record(episode_or_service, stage, envs, stage_verdict,
                                       reasoning_summary, report_md, precedents, fields))

    @mcp.tool()
    def find_similar_episodes(episode_or_service: str, stage: str = "") -> str:
        """Balanced precedents for this rollout: up to 2 healthy and 2
        unhealthy LABELED episodes (labels come from outcomes/humans, never
        from past agent verdicts), hard-filtered for architecture
        compatibility, ranked by fingerprint similarity, scope-widened only
        when the same service has too little history. Precedents inform
        interpretation and what to check next — they never satisfy a policy
        rule and never convert a policy fail into healthy. An
        insufficient_precedent flag means say so rather than guess."""
        episode_id = intel.resolve_episode(episode_or_service, stage) \
            if stage else episode_or_service
        episode = intel.db.one("SELECT * FROM episodes WHERE episode_id=?",
                               (episode_id,)) if episode_id else None
        if not episode:
            return json.dumps({"error": f"no episode resolvable from "
                                        f"{episode_or_service!r} (stage {stage!r})"})
        service = intel.db.one("SELECT * FROM services WHERE service_uid=?",
                               (episode["service_uid"],))
        return json.dumps(retrieval.find_precedents(
            intel.db, service, json.loads(episode["fingerprint_json"]),
            exclude_episode=episode["episode_id"], episode_id=episode["episode_id"]))

    @mcp.tool()
    def get_dossier(service: str, as_of: str = "") -> str:
        """The service's operational dossier: per-field claims with
        epistemic type (approved/observed are governed truth;
        hypothesized/asserted are unverified), confidence, and validity.
        Claims INFORM interpretation — they never satisfy a policy rule
        and never substitute for live evidence. Accepts the svc:// uid or
        the bare service name; as_of (ISO time) reads the dossier as it
        was known at that moment."""
        uid = intel.resolve_service_uid(service)
        if uid is None:
            return json.dumps({"error": f"unknown service {service!r}"})
        result = intel.dossiers.get(uid, as_of or None)
        intel.db.audit_retrieval(None, "get_dossier",
                                 {"service": uid, "as_of": as_of or None},
                                 [c["rev_id"] for c in result["claims"]], as_of or None)
        return json.dumps(result)

    @mcp.tool()
    def propose_dossier_update(service: str, field: str, value_json: str,
                               epistemic_type: str, rationale: str,
                               valid_to: str = "",
                               source_episode_ids: str = "[]") -> str:
        """Propose a dossier fact you observed or hypothesize about this
        service (e.g. a stabilization window, a traffic pattern). Only
        epistemic types 'hypothesized' or 'asserted' are accepted from
        agents, and proposals NEVER go live directly — a human reviews and
        promotes them (or rejects). Cite the episode ids supporting the
        claim in source_episode_ids (a JSON array): only support from
        LABELED episodes counts toward machine promotion suggestions."""
        uid = intel.resolve_service_uid(service)
        if uid is None:
            return json.dumps({"error": f"unknown service {service!r}"})
        try:
            value = json.loads(value_json)
            sources = json.loads(source_episode_ids)
            assert isinstance(sources, list)
        except Exception:
            return json.dumps({"error": "value_json must be valid JSON and "
                                        "source_episode_ids a JSON array"})
        rev = intel.dossiers.propose(uid, field, value, epistemic_type,
                                     valid_to=valid_to or None, rationale=rationale,
                                     sources=sources, agent_originated=True)
        if "error" in rev:
            return json.dumps(rev)
        return json.dumps({"rev_id": rev["rev_id"], "status": rev["status"],
                           "note": "proposal recorded; requires human promotion "
                                   "before it appears in any dossier read"})

    return mcp


# --- REST face -----------------------------------------------------------------


def build_rest(intel: Intel, port: int) -> ThreadingHTTPServer:
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
            qs = parse_qs(parsed.query)
            parts = [p for p in parsed.path.split("/") if p]
            if parsed.path == "/intel/episodes":
                status = (qs.get("status") or [""])[0]
                rows = intel.db.query(
                    "SELECT * FROM episodes WHERE (?='' OR status=?) ORDER BY created_at",
                    (status, status))
                self._send(200, rows)
            elif len(parts) == 3 and parts[:2] == ["intel", "episodes"]:
                episode_id = parts[2]
                episode = intel.db.one("SELECT * FROM episodes WHERE episode_id=?",
                                       (episode_id,))
                if not episode:
                    self._send(404, {"error": "unknown episode"})
                    return
                episode["checkpoints"] = intel.db.query(
                    "SELECT * FROM checkpoints WHERE episode_id=? ORDER BY created_at",
                    (episode_id,))
                episode["observations"] = intel.db.query(
                    """SELECT observation_id,type,sig_verified,observed_at,checkpoint_id
                       FROM observations WHERE episode_id=?""", (episode_id,))
                self._send(200, episode)
            elif parsed.path == "/intel/dossier":
                service = (qs.get("service") or [""])[0]
                as_of = (qs.get("as_of") or [None])[0]
                uid = intel.resolve_service_uid(service) if service else None
                if uid is None:
                    self._send(404, {"error": f"unknown service {service!r}"})
                    return
                self._send(200, intel.dossiers.get(uid, as_of))
            elif parsed.path == "/intel/dossier/journal":
                service = (qs.get("service") or [""])[0]
                uid = intel.resolve_service_uid(service) if service else None
                self._send(200, intel.dossiers.journal(uid))
            elif parsed.path == "/intel/dossier/proposals":
                self._send(200, intel.dossiers.proposals())
            elif parsed.path == "/intel/precedents":
                episode_id = (qs.get("episode") or [""])[0]
                as_of = (qs.get("as_of") or [None])[0]
                episode = intel.db.one("SELECT * FROM episodes WHERE episode_id=?",
                                       (episode_id,))
                if not episode:
                    self._send(404, {"error": f"unknown episode {episode_id!r}"})
                    return
                service = intel.db.one("SELECT * FROM services WHERE service_uid=?",
                                       (episode["service_uid"],))
                self._send(200, retrieval.find_precedents(
                    intel.db, service, json.loads(episode["fingerprint_json"]),
                    as_of=as_of, exclude_episode=episode_id, episode_id=episode_id,
                    tool="replay"))
            elif parsed.path == "/intel/learning/suggestions":
                self._send(200, learning.suggest_promotions(intel.db))
            elif parsed.path == "/intel/learning/signal-utility":
                self._send(200, learning.signal_utility(intel.db))
            elif parsed.path == "/intel/metrics/decision-quality":
                self._send(200, intel.decision_quality())
            elif parsed.path == "/intel/health":
                self._send(200, {"ok": True, "policy": intel.pack.version})
            else:
                self._send(404, {"error": f"unknown GET {parsed.path}"})

        def do_POST(self):  # noqa: N802
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            body = self._body()
            try:
                if parsed.path == "/intel/episodes":
                    self._send(200, intel.create_episode(body))
                elif (len(parts) == 4 and parts[:2] == ["intel", "episodes"]
                        and parts[3] == "checkpoints"):
                    self._send(200, intel.open_checkpoint(
                        parts[2], body["stage"], body.get("session_id", "")))
                elif (len(parts) == 4 and parts[:2] == ["intel", "episodes"]
                        and parts[3] == "outcome"):
                    # Idempotent per (episode, horizon) so a restarted
                    # collector re-observing a horizon updates rather than
                    # duplicates. Unknown episodes 404 (a reset can orphan a
                    # collector thread), and an existing label is never
                    # overwritten — a human's label outranks the collector.
                    episode = intel.db.one(
                        "SELECT final_label FROM episodes WHERE episode_id=?",
                        (parts[2],))
                    if episode is None:
                        self._send(404, {"error": f"unknown episode {parts[2]}"})
                        return
                    intel.db.execute(
                        """INSERT OR REPLACE INTO outcomes(outcome_id,episode_id,horizon,
                           collected_at,slo_json,rollback_detected,rollback_at,
                           incident_refs_json,source,notes)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (f"out_{parts[2]}_{body.get('horizon', 'final')}", parts[2],
                         body.get("horizon", "final"), now_iso(),
                         json.dumps(body.get("slo", {})),
                         1 if body.get("rollback_detected") else 0,
                         body.get("rollback_at"),
                         json.dumps(body.get("incident_refs", [])),
                         body.get("source", "webhook"), body.get("notes", "")))
                    if body.get("final_label") and episode["final_label"] is None:
                        intel.db.execute(
                            """UPDATE episodes SET final_label=?, labeled_at=?, status='closed'
                               WHERE episode_id=? AND final_label IS NULL""",
                            (body["final_label"], now_iso(), parts[2]))
                    self._send(200, {"recorded": True,
                                     "label_applied": bool(body.get("final_label"))
                                     and episode["final_label"] is None})
                elif parsed.path == "/intel/feedback":
                    intel.db.execute(
                        """INSERT INTO feedback(feedback_id,episode_id,type,actor,
                           payload_json,recorded_at) VALUES(?,?,?,?,?,?)""",
                        (f"fb_{now_iso()}", body["episode_id"], body["type"],
                         body.get("actor", ""), json.dumps(body.get("payload", {})),
                         now_iso()))
                    self._send(200, {"recorded": True})
                elif parsed.path == "/intel/dossier/propose":
                    # Operator path: any epistemic type, still lands as
                    # proposed — promotion is a separate deliberate step.
                    uid = intel.resolve_service_uid(body["service"])
                    if uid is None:
                        self._send(404, {"error": f"unknown service {body['service']!r}"})
                        return
                    rev = intel.dossiers.propose(
                        uid, body["field"], body["value"], body["epistemic_type"],
                        confidence=body.get("confidence"),
                        valid_from=body.get("valid_from"), valid_to=body.get("valid_to"),
                        expires_at=body.get("expires_at"),
                        sources=body.get("sources"), rationale=body.get("rationale", ""),
                        agent_originated=False)
                    self._send(400 if "error" in rev else 200, rev)
                elif (len(parts) == 4 and parts[:2] == ["intel", "dossier"]
                        and parts[3] == "promote"):
                    rev = intel.dossiers.activate(
                        parts[2], body.get("verified_by", "operator"),
                        body.get("epistemic_type"))
                    self._send(400 if "error" in rev else 200, rev)
                elif (len(parts) == 4 and parts[:2] == ["intel", "dossier"]
                        and parts[3] == "reject"):
                    rev = intel.dossiers.reject(parts[2], body.get("actor", "operator"))
                    self._send(400 if "error" in rev else 200, rev)
                elif parsed.path == "/intel/dossier/sync":
                    self._send(200, intel.dossiers.sync())
                elif parsed.path == "/intel/fixtures/load":
                    # Test-only: load a labeled episode corpus with FIXED
                    # ids (replay + experiment runs need stable references).
                    # Reloading a fixture episode RESETS it: its old
                    # checkpoints/observations/decisions go away so a
                    # two-arm experiment can be re-armed and re-run.
                    loaded = {"services": 0, "episodes": 0, "checkpoints": 0}
                    for svc in body.get("services", []):
                        intel.db.upsert_service(svc)
                        loaded["services"] += 1
                    known = {e["episode_id"] for e in body.get("episodes", [])}
                    for cp in body.get("open_checkpoints", []):
                        if cp["episode_id"] not in known:
                            raise ValueError(f"checkpoint references unknown fixture "
                                             f"episode {cp['episode_id']}")
                        if cp["stage"] not in STAGE_LADDER:
                            raise ValueError(f"unknown stage {cp['stage']!r}")
                    for ep in body.get("episodes", []):
                        for table in ("decisions",):
                            intel.db.execute(
                                f"""DELETE FROM {table} WHERE checkpoint_id IN
                                    (SELECT checkpoint_id FROM checkpoints WHERE episode_id=?)""",
                                (ep["episode_id"],))
                        intel.db.execute("DELETE FROM observations WHERE episode_id=?",
                                         (ep["episode_id"],))
                        intel.db.execute("DELETE FROM checkpoints WHERE episode_id=?",
                                         (ep["episode_id"],))
                        intel.db.execute(
                            """INSERT OR REPLACE INTO episodes(episode_id,service_uid,
                               revision_from,revision_to,fingerprint_json,deploy_event_json,
                               started_at,status,final_verdict,final_label,labeled_at,
                               architecture_version,created_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ep["episode_id"], ep["service_uid"],
                             ep.get("revision_from", ""), ep.get("revision_to", ""),
                             json.dumps(ep["fingerprint"]),
                             json.dumps(ep.get("deploy_event", {})),
                             ep["started_at"], ep.get("status", "closed"),
                             ep.get("final_verdict"), ep.get("final_label"),
                             ep.get("labeled_at"),
                             ep["fingerprint"].get("architecture_version", ""),
                             ep["started_at"]))
                        loaded["episodes"] += 1
                    for cp in body.get("open_checkpoints", []):
                        intel.db.open_checkpoint(cp["episode_id"], cp["stage"],
                                                 cp.get("session_id", ""), now_iso())
                        loaded["checkpoints"] += 1
                    self._send(200, loaded)
                elif parsed.path == "/intel/replay/reset":
                    db_path = os.environ.get("INTEL_DB", "intel.db")
                    intel.db._conn.close()  # noqa: SLF001 — test-only endpoint
                    if os.path.exists(db_path):
                        os.remove(db_path)
                    intel.__init__(db_path, intel.policy_path, intel.catalog_path)
                    self._send(200, {"reset": True})
                else:
                    self._send(404, {"error": f"unknown POST {parsed.path}"})
            except (KeyError, ValueError) as exc:
                self._send(400, {"error": str(exc)})

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-port", type=int, default=7610)
    ap.add_argument("--rest-port", type=int, default=7611)
    ap.add_argument("--policy", default="../policies/rollout-slo.yaml")
    ap.add_argument("--catalog", default="../catalog/services.yaml")
    args = ap.parse_args()

    intel = Intel(os.environ.get("INTEL_DB", "intel.db"), args.policy, args.catalog)
    rest = build_rest(intel, args.rest_port)
    threading.Thread(target=rest.serve_forever, daemon=True).start()
    print(f"rollout-intel: mcp=:{args.mcp_port} rest=:{args.rest_port} "
          f"policy={intel.pack.version}")
    build_mcp(intel, args.mcp_port).run(transport="streamable-http")


if __name__ == "__main__":
    main()
