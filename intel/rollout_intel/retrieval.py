"""Precedent retrieval: balanced, hard-filtered, audited — never left to
semantic vibes.

The non-negotiables from the memory design:
  - Hard filters first (SQL, not ranking): labeled episodes only — the
    system never treats its own past verdicts as ground truth; a precedent
    exists only once an outcome collector or human labeled it. Bitemporal
    correctness: `labeled_at <= as_of`, so replay can never see a label
    that did not exist yet.
  - Architecture compatibility: an episode from a different
    architecture_version of the same service is history, not precedent.
  - Scope widening ladder, never scope soup: same service -> same service
    family + environment -> same runtime + environment. Each rung is only
    tried when the previous one produced too few candidates, and the rung
    used is recorded in the audit.
  - Balance enforced in SQL/python, not by the model: top-2 healthy and
    top-2 unhealthy by fingerprint Jaccard. If either side is short we
    return fewer and set insufficient_precedent — we never backfill with
    extra same-label episodes, because a one-sided precedent set is how
    confirmation bias gets institutionalized.
  - Every retrieval is journaled to retrieval_audit (what was asked, which
    filters, what came back) so a verdict's provenance can be replayed.
"""

import datetime
import json

from . import fingerprint
from .db import Db

HEALTHY_LABELS = ("healthy",)
UNHEALTHY_LABELS = ("regressed", "rolled_back")

_MIN_PER_SIDE = 2


def to_utc_z(ts: str | None) -> str | None:
    """Normalize an ISO timestamp to UTC 'Z' form. Every stored timestamp
    is already Z (now_iso), but as_of arrives from callers — a +05:30
    offset compared lexicographically against Z strings would silently
    leak future labels into replay."""
    if not ts:
        return ts
    try:
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ts


def _candidates(db: Db, rung: str, service: dict, fp: dict, as_of: str | None,
                exclude_episode: str | None) -> list[dict]:
    where = ["e.final_label IS NOT NULL", "e.labeled_at IS NOT NULL"]
    params: list = []
    if as_of:
        where.append("e.labeled_at <= ?")
        params.append(as_of)
    if exclude_episode:
        where.append("e.episode_id != ?")
        params.append(exclude_episode)
    # Architecture compatibility is a hard filter on every rung, and it is
    # strict: an unknown ('') architecture is only compatible with unknown —
    # "we don't know what this ran on" is not a wildcard.
    where.append("e.architecture_version = ?")
    params.append(fp.get("architecture_version", ""))

    if rung == "service":
        where.append("e.service_uid = ?")
        params.append(service["service_uid"])
    elif rung == "family":
        # Exact family equality from the episode's own fingerprint — a
        # name-prefix LIKE would let family 'demo' swallow 'demo-x-*'.
        where.append("json_extract(e.fingerprint_json,'$.service_family') = ?"
                     " AND s.environment = ?")
        params.extend([fp.get("service_family", ""), service.get("environment", "prod")])
    elif rung == "runtime":
        where.append("s.runtime = ? AND s.environment = ?")
        params.extend([service.get("runtime", "cloud-run"),
                       service.get("environment", "prod")])
    return db.query(
        f"""SELECT e.*, s.name AS service_name FROM episodes e
            JOIN services s ON s.service_uid = e.service_uid
            WHERE {' AND '.join(where)}""", tuple(params))


def find_precedents(db: Db, service: dict, fp: dict, as_of: str | None = None,
                    exclude_episode: str | None = None,
                    episode_id: str | None = None,
                    tool: str = "find_similar_episodes") -> dict:
    as_of = to_utc_z(as_of)
    # Widening is monotonic: each rung ADDS candidates (deduped by id), so
    # reaching for runtime-mates can never lose family-mates already found.
    rung_used = None
    by_id: dict[str, dict] = {}
    for rung in ("service", "family", "runtime"):
        for c in _candidates(db, rung, service, fp, as_of, exclude_episode):
            by_id.setdefault(c["episode_id"], c)
        candidates = list(by_id.values())
        healthy_n = sum(1 for c in candidates if c["final_label"] in HEALTHY_LABELS)
        unhealthy_n = sum(1 for c in candidates if c["final_label"] in UNHEALTHY_LABELS)
        rung_used = rung
        if healthy_n >= _MIN_PER_SIDE and unhealthy_n >= _MIN_PER_SIDE:
            break

    def ranked(labels: tuple) -> list[dict]:
        group = [c for c in candidates if c["final_label"] in labels]
        group.sort(key=lambda c: (-fingerprint.jaccard(fp, json.loads(c["fingerprint_json"])),
                                  c["labeled_at"] or ""))
        return group[:_MIN_PER_SIDE]

    healthy = ranked(HEALTHY_LABELS)
    unhealthy = ranked(UNHEALTHY_LABELS)

    def brief(c: dict) -> dict:
        return {
            "episode_id": c["episode_id"],
            "service": c["service_name"],
            "revision_to": c["revision_to"],
            "final_verdict": c["final_verdict"],
            "final_label": c["final_label"],
            "labeled_at": c["labeled_at"],
            "similarity": round(fingerprint.jaccard(fp, json.loads(c["fingerprint_json"])), 3),
            "fingerprint": json.loads(c["fingerprint_json"]),
        }

    result = {
        "scope_rung": rung_used,
        "healthy": [brief(c) for c in healthy],
        "unhealthy": [brief(c) for c in unhealthy],
        "insufficient_precedent": len(healthy) < _MIN_PER_SIDE or len(unhealthy) < _MIN_PER_SIDE,
        "note": ("Precedents inform interpretation and what to look at next; "
                 "they never satisfy a policy rule and never convert a policy "
                 "fail into a healthy verdict."),
    }
    db.audit_retrieval(
        episode_id, tool,
        {"scope_rung": rung_used, "as_of": as_of,
         "architecture_version": fp.get("architecture_version", ""),
         "exclude": exclude_episode},
        [c["episode_id"] for c in healthy + unhealthy], as_of)
    return result
