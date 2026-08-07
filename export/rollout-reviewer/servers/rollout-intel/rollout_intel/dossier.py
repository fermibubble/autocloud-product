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
import logging
import os
import threading
import urllib.request

from sqlalchemy import func, or_, select, update

from .db import Db, new_id, now_iso, row_dict, to_utc_z
from .models import DossierRevision

log = logging.getLogger("rollout_intel.dossier")

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
        except Exception as exc:
            log.warning("dossier projection failed for %s: %s", rev["rev_id"], exc)
            return None

    def retract(self, memory_id: str) -> bool:
        """Delete a projected memory whose journal revision is no longer
        active. Supersession-by-write handles replaced claims; this is for
        expiry/invalidation, where there is no replacement write to do it."""
        body = json.dumps({
            "id": memory_id,
            "sessionId": "intel-dossier-projection",
            "turn": 0,
        }).encode()
        req = urllib.request.Request(f"{self.api}/v1/memory/delete", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as exc:
            log.warning("dossier retraction failed for %s: %s", memory_id, exc)
            return False


class DossierStore:
    def __init__(self, db: Db, projector: MemoryProjector | None = None):
        self.db = db
        self.projector = projector
        # State transitions are check-then-act sequences over several
        # statements; this lock serializes them so two concurrent
        # promotions can never yield two active revisions of one field.
        self._lock = threading.Lock()

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
        with self.db.session() as s:
            rev = DossierRevision(
                rev_id=rev_id, service_uid=service_uid, field=field,
                value_json=json.dumps(value), epistemic_type=epistemic_type,
                status="proposed", confidence=confidence,
                valid_from=valid_from or now_iso(), valid_to=valid_to,
                recorded_at=now_iso(), expires_at=expires_at,
                sources_json=json.dumps(sources or []), rationale=rationale)
            s.add(rev)
            s.flush()
            return row_dict(rev)

    def activate(self, rev_id: str, verified_by: str,
                 epistemic_type: str | None = None) -> dict:
        with self._lock:
            with self.db.session() as s:
                obj = s.get(DossierRevision, rev_id)
                if obj is None:
                    return {"error": f"unknown revision {rev_id}"}
                if obj.status not in ("proposed",):
                    return {"error": f"revision {rev_id} is {obj.status}, not proposed"}
                now = now_iso()
                if obj.expires_at and obj.expires_at <= now:
                    obj.status = "expired"
                    obj.deactivated_at = now
                    return {"error": f"revision {rev_id} expired at {obj.expires_at}; "
                                     "propose a fresh revision instead"}
                if epistemic_type is not None:
                    if epistemic_type not in EPISTEMIC_TYPES:
                        return {"error": f"epistemic_type must be one of {sorted(EPISTEMIC_TYPES)}"}
                    obj.epistemic_type = epistemic_type
                # memory_id is cleared because the successor's projection WRITE
                # supersedes the old memory in the harness store — retraction
                # is only for expiry, where no replacement write happens.
                s.execute(
                    update(DossierRevision)
                    .where(DossierRevision.service_uid == obj.service_uid,
                           DossierRevision.field == obj.field,
                           DossierRevision.status == "active")
                    .values(status="superseded", superseded_by_rev=rev_id,
                            deactivated_at=now, memory_id=None))
                obj.status = "active"
                obj.owner_verified_by = verified_by
                obj.activated_at = now
                s.flush()
                rev = row_dict(obj)
        if self.projector is not None:
            memory_id = self.projector.project(rev)
            if memory_id:
                with self.db.session() as s:
                    result = s.execute(
                        update(DossierRevision)
                        .where(DossierRevision.rev_id == rev_id,
                               DossierRevision.status == "active")
                        .values(memory_id=memory_id))
                if result.rowcount == 0:
                    # The rev was expired/superseded between commit and
                    # projection - the projection has no owner; retract it.
                    self.projector.retract(memory_id)
                else:
                    rev["memory_id"] = memory_id
        return rev

    def reject(self, rev_id: str, actor: str) -> dict:
        with self._lock:
            with self.db.session() as s:
                obj = s.get(DossierRevision, rev_id)
                if obj is None:
                    return {"error": f"unknown revision {rev_id}"}
                if obj.status != "proposed":
                    return {"error": f"revision {rev_id} is {obj.status}, "
                                     "not proposed"}
                obj.status = "rejected"
                obj.owner_verified_by = actor
                s.flush()
                return row_dict(obj)

    def _retract_projections(self, revs: list[dict]) -> None:
        """Expired/invalidated claims must also leave the memstore
        projection — there is no replacement write to supersede them."""
        if self.projector is None:
            return
        for rev in revs:
            if rev.get("memory_id") and self.projector.retract(rev["memory_id"]):
                with self.db.session() as s:
                    s.execute(
                        update(DossierRevision)
                        .where(DossierRevision.rev_id == rev["rev_id"])
                        .values(memory_id=None))

    def sweep_expired(self) -> int:
        now = now_iso()
        with self._lock:
            with self.db.session() as s:
                doomed = [{"rev_id": rev_id, "memory_id": memory_id}
                          for rev_id, memory_id in s.execute(
                              select(DossierRevision.rev_id, DossierRevision.memory_id)
                              .where(DossierRevision.status == "active",
                                     DossierRevision.expires_at.is_not(None),
                                     DossierRevision.expires_at <= now))]
                expired = s.execute(
                    update(DossierRevision)
                    .where(DossierRevision.status == "active",
                           DossierRevision.expires_at.is_not(None),
                           DossierRevision.expires_at <= now)
                    .values(status="expired", deactivated_at=now)).rowcount
        self._retract_projections(doomed)
        return expired

    def invalidate_architecture(self, service_uid: str, new_arch_version: str) -> int:
        """An architecture change expires architecture-sensitive active
        claims — recorded as expiry (with the deactivation instant), never
        deletion: history stays queryable via as_of."""
        now = now_iso()
        arch_fields = sorted(ARCH_SENSITIVE_FIELDS)
        with self._lock:
            with self.db.session() as s:
                doomed = [{"rev_id": rev_id, "memory_id": memory_id}
                          for rev_id, memory_id in s.execute(
                              select(DossierRevision.rev_id, DossierRevision.memory_id)
                              .where(DossierRevision.service_uid == service_uid,
                                     DossierRevision.status == "active",
                                     DossierRevision.field.in_(arch_fields)))]
                expired = s.execute(
                    update(DossierRevision)
                    .where(DossierRevision.service_uid == service_uid,
                           DossierRevision.status == "active",
                           DossierRevision.field.in_(arch_fields))
                    .values(status="expired", deactivated_at=now,
                            rationale=func.coalesce(DossierRevision.rationale, "").concat(
                                f" [expired: architecture change to {new_arch_version}]"))
                ).rowcount
        self._retract_projections(doomed)
        return expired

    # --- reads ------------------------------------------------------------

    def get(self, service_uid: str, as_of: str | None = None) -> dict:
        """Per-field claims as of a record time (default: now). A revision
        is visible at `as_of` iff it had been activated by then and not yet
        deactivated — deactivated_at is stamped uniformly by supersession,
        expiry sweeps, and architecture invalidation, which is what makes
        replay time-correct (an expired claim never resurrects)."""
        # Stored stamps are Z-form; an offset-form as_of must be
        # normalized before the lexicographic comparisons below.
        as_of = to_utc_z(as_of)
        if as_of is None:
            stmt = (select(DossierRevision)
                    .where(DossierRevision.service_uid == service_uid,
                           DossierRevision.status == "active"))
        else:
            stmt = (select(DossierRevision)
                    .where(DossierRevision.service_uid == service_uid,
                           DossierRevision.activated_at.is_not(None),
                           DossierRevision.activated_at <= as_of,
                           or_(DossierRevision.deactivated_at.is_(None),
                               DossierRevision.deactivated_at > as_of)))
        with self.db.session() as s:
            rows = s.execute(stmt.order_by(DossierRevision.field)).scalars().all()
            claims = [{
                "field": r.field,
                "value": json.loads(r.value_json),
                "epistemic_type": r.epistemic_type,
                "confidence": r.confidence,
                "valid_from": r.valid_from,
                "valid_to": r.valid_to,
                "status": r.status,
                "rev_id": r.rev_id,
                "verified_by": r.owner_verified_by,
            } for r in rows]
        return {"service_uid": service_uid, "as_of": as_of or now_iso(), "claims": claims}

    def governed_value(self, service_uid: str, field: str):
        """The active claim's value, but ONLY if its epistemic type is
        governed truth (approved/observed). Scheduling and any other
        behavior-changing consumer must use this — an asserted or
        hypothesized window shortening real soak time would be the memory
        deciding, not informing."""
        with self.db.session() as s:
            value_json = s.execute(
                select(DossierRevision.value_json)
                .where(DossierRevision.service_uid == service_uid,
                       DossierRevision.field == field,
                       DossierRevision.status == "active",
                       DossierRevision.epistemic_type.in_(("approved", "observed")))
            ).scalars().first()
        return json.loads(value_json) if value_json is not None else None

    def journal(self, service_uid: str | None = None) -> list[dict]:
        stmt = select(DossierRevision).order_by(DossierRevision.recorded_at)
        if service_uid:
            stmt = stmt.where(DossierRevision.service_uid == service_uid)
        with self.db.session() as s:
            return [row_dict(r) for r in s.execute(stmt).scalars()]

    def proposals(self) -> list[dict]:
        with self.db.session() as s:
            return [row_dict(r) for r in s.execute(
                select(DossierRevision)
                .where(DossierRevision.status == "proposed")
                .order_by(DossierRevision.recorded_at)).scalars()]

    def sync(self) -> dict:
        """Repair the projection after a gateway outage: re-project every
        active revision AND retract orphans — non-active revisions whose
        projected memory outlived them (e.g. expiry while the gateway was
        down)."""
        if self.projector is None:
            return {"error": "no projector configured"}
        with self.db.session() as s:
            active = [row_dict(r) for r in s.execute(
                select(DossierRevision)
                .where(DossierRevision.status == "active")).scalars()]
        projected = 0
        for rev in active:
            memory_id = self.projector.project(rev)
            if memory_id:
                with self.db.session() as s:
                    s.execute(
                        update(DossierRevision)
                        .where(DossierRevision.rev_id == rev["rev_id"])
                        .values(memory_id=memory_id))
                projected += 1
        with self.db.session() as s:
            orphans = [{"rev_id": rev_id, "memory_id": memory_id}
                       for rev_id, memory_id in s.execute(
                           select(DossierRevision.rev_id, DossierRevision.memory_id)
                           .where(DossierRevision.status != "active",
                                  DossierRevision.memory_id.is_not(None)))]
        self._retract_projections(orphans)
        return {"active": len(active), "projected": projected,
                "orphans_retracted": len(orphans)}
