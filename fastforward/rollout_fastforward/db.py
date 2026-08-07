"""SQLite persistence for Rollout Fast-Forward.

Integrity lives HERE, not in callers: set_state routes every transition
through states.validate_transition (terminal states immutable),
write_snapshot_once enforces the decision-time snapshot being written
exactly once, and result envelopes only leave via envelopes_for_episode
once their request is terminal — a half-finished run can never feed policy.
"""

import json
import sqlite3
import threading
import time
import uuid

from .manifest import canonicalize, digest
from .states import STATES, TERMINAL, validate_transition

_STATE_SQL = ",".join(f"'{s}'" for s in STATES)
_TERMINAL_SQL = ",".join(f"'{s}'" for s in sorted(TERMINAL))
_CLASS_SQL = ",".join(f"'{c}'" for c in (
    "resource_lifecycle", "rate_balance", "clock_expiry",
    "state_boundary", "concurrency", "agent_longevity"))

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS ff_requests(
  request_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL,
  service TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  manifest_digest TEXT NOT NULL,
  deadline_at TEXT,
  deadline_s REAL,
  budget_json TEXT,
  state TEXT NOT NULL CHECK(state IN ({_STATE_SQL})),
  outcome TEXT,
  snapshot_json TEXT,
  created_at TEXT NOT NULL,
  decided_at TEXT);

CREATE TABLE IF NOT EXISTS hazards(
  hazard_id TEXT NOT NULL,
  request_id TEXT NOT NULL REFERENCES ff_requests(request_id),
  class TEXT NOT NULL CHECK(class IN ({_CLASS_SQL})),
  source TEXT CHECK(source IN ('floor','proposed')),
  features_json TEXT DEFAULT '[]',
  age_dimensions_json TEXT DEFAULT '[]',
  expected_symptom TEXT,
  experiments_json TEXT DEFAULT '[]',
  min_fidelity_json TEXT DEFAULT '{{}}',
  impact TEXT,
  decision_relevance REAL,
  status TEXT,
  PRIMARY KEY(hazard_id, request_id));

CREATE TABLE IF NOT EXISTS plan_steps(
  step_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  hazard_id TEXT,
  mode TEXT CHECK(mode IN ('signal','probe','twin')),
  template TEXT,
  cost_est_s REAL,
  run_if TEXT,
  state TEXT,
  result_json TEXT,
  started_at TEXT,
  ended_at TEXT);

CREATE TABLE IF NOT EXISTS probe_runs(
  run_id TEXT PRIMARY KEY,
  step_id TEXT NOT NULL,
  instance_id TEXT,
  seed INTEGER,
  measurements_json TEXT,
  side_effects_json TEXT,
  stop_reason TEXT,
  started_at TEXT,
  ended_at TEXT);

CREATE TABLE IF NOT EXISTS stable_profiles(
  profile_id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  template TEXT NOT NULL,
  env_fingerprint_json TEXT NOT NULL,
  stats_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  source TEXT);

CREATE TABLE IF NOT EXISTS counterexamples(
  cx_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  hazard_id TEXT,
  candidate_digest TEXT,
  template TEXT,
  state_slice_digest TEXT,
  event_sequence_json TEXT,
  expected_stable_json TEXT,
  observed_candidate_json TEXT,
  first_divergence_age_json TEXT,
  replay_seed INTEGER,
  replay_verified INTEGER DEFAULT 0,
  created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ff_envelopes(
  observation_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  type TEXT,
  envelope_json TEXT NOT NULL,
  minted_at TEXT NOT NULL);
"""

_STEP_FIELDS = {"hazard_id", "mode", "template", "cost_est_s", "run_if",
                "state", "result_json", "started_at", "ended_at"}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Db:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
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

    # --- requests ---------------------------------------------------------

    def create_request(self, episode_id: str, service: str, manifest: dict,
                       deadline_s: float, budget: dict) -> dict:
        request_id = new_id("ffr")
        canonical = canonicalize(manifest)
        self.execute(
            """INSERT INTO ff_requests(request_id,episode_id,service,manifest_json,
               manifest_digest,deadline_at,deadline_s,budget_json,state,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (request_id, episode_id, service, json.dumps(canonical), digest(canonical),
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + deadline_s)),
             float(deadline_s), json.dumps(budget or {}), "RECEIVED", now_iso()),
        )
        return self.get_request(request_id)

    def get_request(self, request_id: str) -> dict | None:
        return self.one("SELECT * FROM ff_requests WHERE request_id=?", (request_id,))

    def set_state(self, request_id: str, new_state: str) -> dict:
        row = self.get_request(request_id)
        if row is None:
            raise ValueError(f"unknown request {request_id}")
        validate_transition(row["state"], new_state)
        if new_state in TERMINAL:
            self.execute("UPDATE ff_requests SET state=?, decided_at=? WHERE request_id=?",
                         (new_state, now_iso(), request_id))
        else:
            self.execute("UPDATE ff_requests SET state=? WHERE request_id=?",
                         (new_state, request_id))
        return self.get_request(request_id)

    def write_snapshot_once(self, request_id: str, snapshot: dict) -> None:
        if self.get_request(request_id) is None:
            raise ValueError(f"unknown request {request_id}")
        cur = self.execute(
            "UPDATE ff_requests SET snapshot_json=? WHERE request_id=? AND snapshot_json IS NULL",
            (json.dumps(snapshot), request_id))
        if cur.rowcount == 0:
            raise ValueError(f"snapshot already written for {request_id}")

    def set_outcome(self, request_id: str, outcome: str) -> None:
        self.execute("UPDATE ff_requests SET outcome=? WHERE request_id=?",
                     (outcome, request_id))

    # --- hazards ----------------------------------------------------------

    def insert_hazard(self, request_id: str, hazard: dict) -> None:
        self.execute(
            """INSERT OR REPLACE INTO hazards(hazard_id,request_id,class,source,
               features_json,age_dimensions_json,expected_symptom,experiments_json,
               min_fidelity_json,impact,decision_relevance,status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (hazard["hazard_id"], request_id, hazard["class"],
             hazard.get("source", "floor"),
             json.dumps(hazard.get("features", [])),
             json.dumps(hazard.get("age_dimensions", [])),
             hazard.get("expected_symptom"),
             json.dumps(hazard.get("experiments", [])),
             json.dumps(hazard.get("min_fidelity", {})),
             hazard.get("impact"), hazard.get("decision_relevance"),
             hazard.get("status", "compiled")),
        )

    def hazards_for(self, request_id: str) -> list[dict]:
        rows = self.query("SELECT * FROM hazards WHERE request_id=? ORDER BY hazard_id",
                          (request_id,))
        return [{
            "hazard_id": r["hazard_id"], "class": r["class"], "source": r["source"],
            "features": json.loads(r["features_json"] or "[]"),
            "age_dimensions": json.loads(r["age_dimensions_json"] or "[]"),
            "expected_symptom": r["expected_symptom"],
            "experiments": json.loads(r["experiments_json"] or "[]"),
            "min_fidelity": json.loads(r["min_fidelity_json"] or "{}"),
            "impact": r["impact"], "decision_relevance": r["decision_relevance"],
            "status": r["status"],
        } for r in rows]

    # --- plan steps / probe runs -----------------------------------------

    def insert_plan_step(self, request_id: str, step: dict) -> str:
        step_id = step.get("step_id") or new_id("st")
        self.execute(
            """INSERT INTO plan_steps(step_id,request_id,hazard_id,mode,template,
               cost_est_s,run_if,state,result_json,started_at,ended_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (step_id, request_id, step.get("hazard_id"), step.get("mode"),
             step.get("template"), step.get("cost_est_s"), step.get("run_if"),
             step.get("state", "pending"),
             json.dumps(step["result"]) if "result" in step else None,
             step.get("started_at"), step.get("ended_at")),
        )
        return step_id

    def update_step(self, step_id: str, fields: dict) -> None:
        cols, vals = [], []
        for k, v in fields.items():
            if k == "result":
                k, v = "result_json", json.dumps(v)
            if k not in _STEP_FIELDS:
                raise ValueError(f"unknown step field {k}")
            cols.append(f"{k}=?")
            vals.append(v)
        if cols:
            self.execute(f"UPDATE plan_steps SET {','.join(cols)} WHERE step_id=?",
                         (*vals, step_id))

    def steps_for(self, request_id: str) -> list[dict]:
        rows = self.query("SELECT * FROM plan_steps WHERE request_id=? ORDER BY step_id",
                          (request_id,))
        for r in rows:
            r["result"] = json.loads(r.pop("result_json") or "null")
        return rows

    def insert_probe_run(self, step_id: str, run: dict) -> str:
        run_id = run.get("run_id") or new_id("pr")
        self.execute(
            """INSERT INTO probe_runs(run_id,step_id,instance_id,seed,measurements_json,
               side_effects_json,stop_reason,started_at,ended_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (run_id, step_id, run.get("instance_id"), run.get("seed"),
             json.dumps(run.get("measurements", {})),
             json.dumps(run.get("side_effects", [])),
             run.get("stop_reason"), run.get("started_at"), run.get("ended_at")),
        )
        return run_id

    # --- stable profiles --------------------------------------------------

    def insert_profile(self, service: str, template: str, env_fingerprint: dict,
                       stats: dict, expires_at: str, source: str = "probe") -> str:
        profile_id = new_id("prof")
        self.execute(
            """INSERT INTO stable_profiles(profile_id,service,template,env_fingerprint_json,
               stats_json,created_at,expires_at,source) VALUES(?,?,?,?,?,?,?,?)""",
            (profile_id, service, template, json.dumps(env_fingerprint),
             json.dumps(stats), now_iso(), expires_at, source),
        )
        return profile_id

    def find_profile(self, service: str, template: str, env_fingerprint: dict,
                     now: str) -> dict | None:
        """Newest live profile whose fingerprint is compatible; None on
        expiry or mismatch — a stale/foreign baseline must not be compared."""
        from .profiles import compatible  # local import: profiles builds on db
        rows = self.query(
            """SELECT * FROM stable_profiles WHERE service=? AND template=?
               ORDER BY created_at DESC, profile_id DESC""", (service, template))
        for r in rows:
            if r["expires_at"] and r["expires_at"] <= now:
                continue
            fp = json.loads(r["env_fingerprint_json"])
            if not compatible(fp, env_fingerprint):
                continue
            return {"profile_id": r["profile_id"], "service": r["service"],
                    "template": r["template"], "env_fingerprint": fp,
                    "stats": json.loads(r["stats_json"]),
                    "created_at": r["created_at"], "expires_at": r["expires_at"],
                    "source": r["source"]}
        return None

    # --- counterexamples --------------------------------------------------

    def insert_counterexample(self, request_id: str, cx: dict) -> str:
        cx_id = cx.get("cx_id") or new_id("cx")
        self.execute(
            """INSERT INTO counterexamples(cx_id,request_id,hazard_id,candidate_digest,
               template,state_slice_digest,event_sequence_json,expected_stable_json,
               observed_candidate_json,first_divergence_age_json,replay_seed,
               replay_verified,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cx_id, request_id, cx.get("hazard_id"), cx.get("candidate_digest"),
             cx.get("template"), cx.get("state_slice_digest"),
             json.dumps(cx.get("event_sequence", [])),
             json.dumps(cx.get("expected_stable")),
             json.dumps(cx.get("observed_candidate")),
             json.dumps(cx.get("first_divergence_age")),
             cx.get("replay_seed"), 1 if cx.get("replay_verified") else 0, now_iso()),
        )
        return cx_id

    def get_counterexample(self, cx_id: str) -> dict | None:
        r = self.one("SELECT * FROM counterexamples WHERE cx_id=?", (cx_id,))
        if r is None:
            return None
        return {"cx_id": r["cx_id"], "request_id": r["request_id"],
                "hazard_id": r["hazard_id"], "candidate_digest": r["candidate_digest"],
                "template": r["template"], "state_slice_digest": r["state_slice_digest"],
                "event_sequence": json.loads(r["event_sequence_json"] or "[]"),
                "expected_stable": json.loads(r["expected_stable_json"] or "null"),
                "observed_candidate": json.loads(r["observed_candidate_json"] or "null"),
                "first_divergence_age": json.loads(r["first_divergence_age_json"] or "null"),
                "replay_seed": r["replay_seed"],
                "replay_verified": bool(r["replay_verified"]),
                "created_at": r["created_at"]}

    def mark_replay_verified(self, cx_id: str,
                             first_divergence_age: dict | None = None) -> None:
        if first_divergence_age is not None:
            self.execute(
                "UPDATE counterexamples SET replay_verified=1, first_divergence_age_json=? WHERE cx_id=?",
                (json.dumps(first_divergence_age), cx_id))
        else:
            self.execute("UPDATE counterexamples SET replay_verified=1 WHERE cx_id=?",
                         (cx_id,))

    # --- envelopes --------------------------------------------------------

    def insert_envelope(self, request_id: str, episode_id: str, env: dict) -> None:
        self.execute(
            """INSERT OR IGNORE INTO ff_envelopes(observation_id,request_id,episode_id,
               type,envelope_json,minted_at) VALUES(?,?,?,?,?,?)""",
            (env["observation_id"], request_id, episode_id, env.get("type"),
             json.dumps(env), now_iso()),
        )

    def envelopes_for_episode(self, episode_id: str, terminal_only: bool = True) -> list[dict]:
        sql = ("SELECT e.envelope_json FROM ff_envelopes e "
               "JOIN ff_requests r ON r.request_id = e.request_id "
               "WHERE e.episode_id=? ")
        if terminal_only:
            sql += f"AND r.state IN ({_TERMINAL_SQL}) "
        sql += "ORDER BY e.minted_at, e.observation_id"
        return [json.loads(r["envelope_json"]) for r in self.query(sql, (episode_id,))]
