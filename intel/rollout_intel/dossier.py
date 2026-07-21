"""Service Operational Dossier: the bitemporal journal is the truth here;
the harness memory store is a read-only projection of it.

Every write lands in dossier_journal as a revision with an epistemic type
(approved | observed | asserted | inferred | hypothesized | rejected), a
status lifecycle (proposed -> active -> superseded/rejected/expired),
domain validity (valid_from/valid_to) and record time (recorded_at /
activated_at). Only ACTIVE revisions project into the harness store
`memstore://project/rollout-dossiers` — one semantic topic per field
(`dossier:<name>.<env>.<region>:<field>`), so harness topic-supersession
mirrors journal supersession, and the reviewer attaches the store
read-only: the agent can consult dossiers, structurally never write them
("never learn from the agent's own verdicts" enforced by schema, not
prompt).

Agent-originated proposals (propose_dossier_update) may carry only the
hypothesized | asserted epistemic types and always land as `proposed` —
a human promotes them via intelctl / REST, which is what stamps
owner_verified_by and (optionally) upgrades the epistemic type.
"""

import json
import os
import urllib.request

from .db import Db, new_id, now_iso

# Epistemic types the AGENT may propose. approved/observed/inferred are
# reserved for governed paths (human promotion, the future outcome
# collector) — an LLM cannot self-certify observation or approval.
AGENT_PROPOSABLE = {"hypothesized", "asserted"}
EPISTEMIC_TYPES = {"approved", "observed", "asserted", "inferred", "hypothesized", "rejected"}

# Fields whose values describe behavior of a specific architecture; an
# architecture_version change expires them rather than letting a stale
# envelope masquerade as current truth.
ARCH_SENSITIVE_FIELDS = {
    "p99_baseline_ms", "error_rate_baseline", "stabilization_window_minutes",
    "traffic_profile", "resource_envelope",
}


def topic_for(service_uid: str, field: str) -> str:
    # svc://autocloud/<name>/<env>/<region> -> dossier:<name>.<env>.<region>:<field>
    parts = service_uid.split("/")
    name, env, region = parts[-3], parts[-2], parts[-1]
    return f"dossier:{name}.{env}.{region}:{field}"


class MemoryProjector:
    """Projects active journal revisions into the harness memory store.

    Best-effort by design: the journal is authoritative, so a gateway
    outage degrades the projection (repaired by `intelctl dossier sync`),
    never the record.
    """

    def __init__(self, api_base: str | None = None, token: str | None = None,
                 store_ref: str = "memstore://project/rollout-dossiers",
                 agent: str = "rollout-reviewer"):
        self.api = (api_base or os.environ.get("ENSEMBLE_API", "http://localhost:8088")).rstrip("/")
        self.token = token or os.environ.get("ENSEMBLE_TOKEN", "")
        self.store_ref = store_ref
        self.agent = agent

    def project(self, rev: dict) -> str | None:
        claim = {
            "field": rev["field"],
            "value": json.loads(rev["value_json"]),
            "epistemic_type": rev["epistemic_type"],
            "confidence": rev["confidence"],
            "valid_from": rev["valid_from"],
            "valid_to": rev["valid_to"],
            "sources": json.loads(rev["sources_json"] or "[]"),
            "rev_id": rev["rev_id"],
            "service_uid": rev["service_uid"],
        }
        body = json.dumps({
            "agent": self.agent,
            "ref": self.store_ref,
            "kind": "semantic",
            "topic": topic_for(rev["service_uid"], rev["field"]),
            "content": json.dumps(claim),
            "sessionId": "intel-dossier-projection",
            "turn": 0,
        }).encode()
        req = urllib.request.Request(f"{self.api}/v1/memory/write", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.load(resp).get("id")
        except Exception:
            return None


class DossierStore:
    def __init__(self, db: Db, projector: MemoryProjector | None = None):
        self.db = db
        self.projector = projector

    # --- writes -----------------------------------------------------------

    def propose(self, service_uid: str, field: str, value, epistemic_type: str,
                confidence: float | None = None, valid_from: str | None = None,
                valid_to: str | None = None, expires_at: str | None = None,
                sources: list | None = None, rationale: str = "",
                agent_originated: bool = True) -> dict:
        if epistemic_type not in EPISTEMIC_TYPES:
            return {"error": f"epistemic_type must be one of {sorted(EPISTEMIC_TYPES)}"}
        if agent_originated and epistemic_type not in AGENT_PROPOSABLE:
            return {"error": (f"agents may propose only {sorted(AGENT_PROPOSABLE)}; "
                              f"{epistemic_type!r} requires the governed promotion path")}
        rev_id = new_id("rev")
        self.db.execute(
            """INSERT INTO dossier_journal(rev_id,service_uid,field,value_json,
               epistemic_type,status,confidence,valid_from,valid_to,recorded_at,
               expires_at,sources_json,rationale) VALUES(?,?,?,?,?,'proposed',?,?,?,?,?,?,?)""",
            (rev_id, service_uid, field, json.dumps(value), epistemic_type,
             confidence, valid_from or now_iso(), valid_to, now_iso(),
             expires_at, json.dumps(sources or []), rationale))
        return self.db.one("SELECT * FROM dossier_journal WHERE rev_id=?", (rev_id,))

    def activate(self, rev_id: str, verified_by: str,
                 epistemic_type: str | None = None) -> dict:
        rev = self.db.one("SELECT * FROM dossier_journal WHERE rev_id=?", (rev_id,))
        if not rev:
            return {"error": f"unknown revision {rev_id}"}
        if rev["status"] not in ("proposed",):
            return {"error": f"revision {rev_id} is {rev['status']}, not proposed"}
        if epistemic_type is not None:
            if epistemic_type not in EPISTEMIC_TYPES:
                return {"error": f"epistemic_type must be one of {sorted(EPISTEMIC_TYPES)}"}
            self.db.execute("UPDATE dossier_journal SET epistemic_type=? WHERE rev_id=?",
                            (epistemic_type, rev_id))
        now = now_iso()
        self.db.execute(
            """UPDATE dossier_journal SET status='superseded', superseded_by_rev=?
               WHERE service_uid=? AND field=? AND status='active'""",
            (rev_id, rev["service_uid"], rev["field"]))
        self.db.execute(
            """UPDATE dossier_journal SET status='active', owner_verified_by=?,
               activated_at=? WHERE rev_id=?""",
            (verified_by, now, rev_id))
        rev = self.db.one("SELECT * FROM dossier_journal WHERE rev_id=?", (rev_id,))
        if self.projector is not None:
            memory_id = self.projector.project(rev)
            if memory_id:
                self.db.execute("UPDATE dossier_journal SET memory_id=? WHERE rev_id=?",
                                (memory_id, rev_id))
                rev["memory_id"] = memory_id
        return rev

    def reject(self, rev_id: str, actor: str) -> dict:
        self.db.execute(
            "UPDATE dossier_journal SET status='rejected', owner_verified_by=? "
            "WHERE rev_id=? AND status='proposed'", (actor, rev_id))
        return self.db.one("SELECT * FROM dossier_journal WHERE rev_id=?", (rev_id,)) or \
            {"error": f"unknown revision {rev_id}"}

    def sweep_expired(self) -> int:
        now = now_iso()
        cur = self.db.execute(
            "UPDATE dossier_journal SET status='expired' "
            "WHERE status='active' AND expires_at IS NOT NULL AND expires_at <= ?", (now,))
        return cur.rowcount

    def invalidate_architecture(self, service_uid: str, new_arch_version: str) -> int:
        """An architecture change expires architecture-sensitive active
        claims — recorded as expiry, never deletion (the journal is
        append-only in spirit; history stays queryable via as_of)."""
        placeholders = ",".join("?" for _ in ARCH_SENSITIVE_FIELDS)
        cur = self.db.execute(
            f"""UPDATE dossier_journal SET status='expired',
                rationale = COALESCE(rationale,'') || ' [expired: architecture change to '||?||']'
                WHERE service_uid=? AND status='active' AND field IN ({placeholders})""",
            (new_arch_version, service_uid, *sorted(ARCH_SENSITIVE_FIELDS)))
        return cur.rowcount

    # --- reads ------------------------------------------------------------

    def get(self, service_uid: str, as_of: str | None = None) -> dict:
        """Per-field claims as of a record time (default: now). A revision
        is visible at `as_of` if it had been activated by then and had not
        yet been superseded — superseded_by_rev's activation time is the
        deactivation instant, which is what makes replay time-correct."""
        if as_of is None:
            rows = self.db.query(
                "SELECT * FROM dossier_journal WHERE service_uid=? AND status='active' "
                "ORDER BY field", (service_uid,))
        else:
            rows = self.db.query(
                """SELECT j.* FROM dossier_journal j
                   WHERE j.service_uid=? AND j.activated_at IS NOT NULL
                     AND j.activated_at <= ?
                     AND j.status IN ('active','superseded','expired')
                     AND NOT EXISTS (
                       SELECT 1 FROM dossier_journal s
                       WHERE s.rev_id = j.superseded_by_rev AND s.activated_at <= ?)
                   ORDER BY j.field""", (service_uid, as_of, as_of))
        claims = [{
            "field": r["field"],
            "value": json.loads(r["value_json"]),
            "epistemic_type": r["epistemic_type"],
            "confidence": r["confidence"],
            "valid_from": r["valid_from"],
            "valid_to": r["valid_to"],
            "status": r["status"],
            "rev_id": r["rev_id"],
            "verified_by": r["owner_verified_by"],
        } for r in rows]
        return {"service_uid": service_uid, "as_of": as_of or now_iso(), "claims": claims}

    def journal(self, service_uid: str | None = None) -> list[dict]:
        if service_uid:
            return self.db.query(
                "SELECT * FROM dossier_journal WHERE service_uid=? ORDER BY recorded_at",
                (service_uid,))
        return self.db.query("SELECT * FROM dossier_journal ORDER BY recorded_at")

    def proposals(self) -> list[dict]:
        return self.db.query(
            "SELECT * FROM dossier_journal WHERE status='proposed' ORDER BY recorded_at")

    def sync(self) -> dict:
        """Re-project every active revision (gateway-outage repair)."""
        if self.projector is None:
            return {"error": "no projector configured"}
        active = self.db.query("SELECT * FROM dossier_journal WHERE status='active'")
        projected = 0
        for rev in active:
            memory_id = self.projector.project(rev)
            if memory_id:
                self.db.execute("UPDATE dossier_journal SET memory_id=? WHERE rev_id=?",
                                (memory_id, rev["rev_id"]))
                projected += 1
        return {"active": len(active), "projected": projected}
