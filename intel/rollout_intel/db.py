"""SQLite persistence for the Rollout Intelligence Layer.

Append-only by policy: nothing here UPDATEs history — episodes advance
status, checkpoints complete once, everything else only inserts. The
final_verdict (what the agent concluded) and final_label (what the outcome
proved) are deliberately separate columns: learning joins on final_label
IS NOT NULL, so the agent can never learn from its own verdicts.
"""

import json
import sqlite3
import threading
import time
import uuid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS services(
  service_uid TEXT PRIMARY KEY,
  name TEXT NOT NULL, environment TEXT NOT NULL, region TEXT NOT NULL,
  runtime TEXT, architecture_version TEXT, owner TEXT,
  aliases_json TEXT DEFAULT '[]',
  source TEXT CHECK(source IN ('catalog','labels','platform','inferred')),
  status TEXT CHECK(status IN ('confirmed','candidate')) DEFAULT 'candidate',
  confirmed_by TEXT, confirmed_at TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS episodes(
  episode_id TEXT PRIMARY KEY,
  service_uid TEXT NOT NULL REFERENCES services(service_uid),
  revision_from TEXT, revision_to TEXT,
  fingerprint_json TEXT NOT NULL,
  deploy_event_json TEXT NOT NULL,
  started_at TEXT NOT NULL,
  status TEXT CHECK(status IN ('open','in_progress','awaiting_outcome','closed')) DEFAULT 'open',
  final_verdict TEXT,
  final_label TEXT,
  labeled_at TEXT,
  architecture_version TEXT,
  created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS checkpoints(
  checkpoint_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
  stage TEXT NOT NULL,
  scheduled_at TEXT, session_id TEXT, completed_at TEXT,
  stage_verdict TEXT, policy_status TEXT, policy_version TEXT,
  policy_conflict INTEGER DEFAULT 0,
  report_version INTEGER, report_md TEXT, next_check_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(episode_id, stage));

CREATE TABLE IF NOT EXISTS observations(
  observation_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL, checkpoint_id TEXT,
  type TEXT NOT NULL, scope_json TEXT, observed_at TEXT, fresh_until TEXT,
  source TEXT, payload_json TEXT, quality_json TEXT,
  content_hash TEXT, sig_verified INTEGER NOT NULL,
  recorded_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS decisions(
  decision_id TEXT PRIMARY KEY,
  checkpoint_id TEXT NOT NULL REFERENCES checkpoints(checkpoint_id),
  kind TEXT CHECK(kind IN ('stage_verdict','final_verdict','escalation','next_check')),
  value_json TEXT NOT NULL, inputs_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS outcomes(
  outcome_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
  horizon TEXT CHECK(horizon IN ('30m','2h','24h','final')),
  collected_at TEXT NOT NULL, slo_json TEXT,
  rollback_detected INTEGER DEFAULT 0, rollback_at TEXT,
  incident_refs_json TEXT DEFAULT '[]',
  source TEXT CHECK(source IN ('collector','webhook','human')),
  notes TEXT);

CREATE TABLE IF NOT EXISTS feedback(
  feedback_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL,
  type TEXT CHECK(type IN ('human_override','human_confirm','incident_link','root_cause')),
  actor TEXT, payload_json TEXT, recorded_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS dossier_journal(
  rev_id TEXT PRIMARY KEY,
  service_uid TEXT NOT NULL,
  field TEXT NOT NULL,
  value_json TEXT NOT NULL,
  epistemic_type TEXT CHECK(epistemic_type IN
    ('approved','observed','asserted','inferred','hypothesized','rejected')),
  status TEXT CHECK(status IN ('proposed','active','superseded','rejected','expired')),
  confidence REAL, valid_from TEXT, valid_to TEXT,
  recorded_at TEXT NOT NULL, expires_at TEXT,
  sources_json TEXT DEFAULT '[]', rationale TEXT,
  owner_verified_by TEXT, superseded_by_rev TEXT, memory_id TEXT,
  activated_at TEXT, deactivated_at TEXT);

CREATE TABLE IF NOT EXISTS retrieval_audit(
  query_id TEXT PRIMARY KEY,
  episode_id TEXT, tool TEXT NOT NULL, filters_json TEXT,
  returned_ids_json TEXT, as_of TEXT, at TEXT NOT NULL);
"""

STAGE_LADDER = ["T+0", "T+5", "T+15", "T+30"]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Db:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        # Dev DBs created before the dossier layer lack the bitemporal
        # columns (CREATE IF NOT EXISTS never alters); patch in place.
        for col in ("activated_at", "deactivated_at"):
            try:
                self._conn.execute(f"ALTER TABLE dossier_journal ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        self._lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # --- services / identity ---------------------------------------------

    def upsert_service(self, svc: dict) -> None:
        self.execute(
            """INSERT INTO services(service_uid,name,environment,region,runtime,
               architecture_version,owner,aliases_json,source,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(service_uid) DO UPDATE SET
                 runtime=excluded.runtime,
                 architecture_version=excluded.architecture_version,
                 owner=excluded.owner""",
            (svc["service_uid"], svc["name"], svc["environment"], svc["region"],
             svc.get("runtime", ""), svc.get("architecture_version", ""),
             svc.get("owner", ""), json.dumps(svc.get("aliases", [])),
             svc.get("source", "catalog"), svc.get("status", "confirmed"), now_iso()),
        )

    # --- episodes / checkpoints -------------------------------------------

    def create_episode(self, service_uid: str, fingerprint: dict, deploy_event: dict) -> dict:
        episode_id = new_id("ep")
        arch = self.one("SELECT architecture_version FROM services WHERE service_uid=?",
                        (service_uid,)) or {}
        self.execute(
            """INSERT INTO episodes(episode_id,service_uid,revision_from,revision_to,
               fingerprint_json,deploy_event_json,started_at,status,architecture_version,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (episode_id, service_uid,
             deploy_event.get("from_revision", ""), deploy_event.get("to_revision", ""),
             json.dumps(fingerprint), json.dumps(deploy_event), now_iso(), "open",
             arch.get("architecture_version", ""), now_iso()),
        )
        return self.one("SELECT * FROM episodes WHERE episode_id=?", (episode_id,))

    def open_checkpoint(self, episode_id: str, stage: str, session_id: str,
                        scheduled_at: str) -> dict:
        checkpoint_id = new_id("cp")
        self.execute(
            """INSERT INTO checkpoints(checkpoint_id,episode_id,stage,scheduled_at,
               session_id,created_at) VALUES(?,?,?,?,?,?)""",
            (checkpoint_id, episode_id, stage, scheduled_at, session_id, now_iso()),
        )
        self.execute("UPDATE episodes SET status='in_progress' WHERE episode_id=? AND status='open'",
                     (episode_id,))
        return self.one("SELECT * FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,))

    def complete_checkpoint(self, checkpoint_id: str, stage_verdict: str, policy_status: str,
                            policy_version: str, policy_conflict: bool, report_md: str,
                            next_check_at: str | None) -> dict:
        row = self.one("SELECT * FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,))
        episode_id = row["episode_id"]
        version = 1 + (self.one(
            "SELECT COALESCE(MAX(report_version),0) AS v FROM checkpoints WHERE episode_id=?",
            (episode_id,))["v"] or 0)
        self.execute(
            """UPDATE checkpoints SET completed_at=?, stage_verdict=?, policy_status=?,
               policy_version=?, policy_conflict=?, report_version=?, report_md=?, next_check_at=?
               WHERE checkpoint_id=? AND completed_at IS NULL""",
            (now_iso(), stage_verdict, policy_status, policy_version,
             1 if policy_conflict else 0, version, report_md, next_check_at, checkpoint_id),
        )
        # The ladder ends when there is no next check — either the last
        # ladder stage, or a governed stabilization window ended it early
        # (dynamic scheduling). Closing keys off next_check_at, not stage.
        if next_check_at is None:
            self.execute(
                "UPDATE episodes SET status='awaiting_outcome', final_verdict=? WHERE episode_id=?",
                (stage_verdict, episode_id),
            )
        return self.one("SELECT * FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,))

    def insert_observation(self, episode_id: str, checkpoint_id: str, env: dict,
                           verified: bool) -> None:
        self.execute(
            """INSERT OR IGNORE INTO observations(observation_id,episode_id,checkpoint_id,type,
               scope_json,observed_at,fresh_until,source,payload_json,quality_json,
               content_hash,sig_verified,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (env.get("observation_id", new_id("obs")), episode_id, checkpoint_id,
             env.get("type", "unknown"), json.dumps(env.get("scope", {})),
             env.get("observed_at"), env.get("fresh_until"), env.get("source"),
             json.dumps(env.get("payload")), json.dumps(env.get("quality", {})),
             env.get("content_hash"), 1 if verified else 0, now_iso()),
        )

    def insert_decision(self, checkpoint_id: str, kind: str, value: dict, inputs: dict) -> None:
        self.execute(
            """INSERT INTO decisions(decision_id,checkpoint_id,kind,value_json,inputs_json,recorded_at)
               VALUES(?,?,?,?,?,?)""",
            (new_id("dec"), checkpoint_id, kind, json.dumps(value), json.dumps(inputs), now_iso()),
        )

    def audit_retrieval(self, episode_id: str | None, tool: str, filters: dict,
                        returned_ids: list[str], as_of: str | None) -> None:
        self.execute(
            """INSERT INTO retrieval_audit(query_id,episode_id,tool,filters_json,
               returned_ids_json,as_of,at) VALUES(?,?,?,?,?,?,?)""",
            (new_id("q"), episode_id, tool, json.dumps(filters),
             json.dumps(returned_ids), as_of, now_iso()),
        )
