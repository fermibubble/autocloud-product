"""Persistence for the Rollout Intelligence Layer — SQLAlchemy 2.0.

Append-only by policy: nothing here UPDATEs history — episodes advance
status, checkpoints complete once, everything else only inserts. The
final_verdict (what the agent concluded) and final_label (what the
outcome proved) are deliberately separate columns: learning joins on
final_label IS NOT NULL, so the agent can never learn from its own
verdicts.

Storage engine: SQLite by default (a bare path in INTEL_DB), any
SQLAlchemy URL otherwise (`postgresql+psycopg://…` points the same
models at a central store). (Two SQLite-isms remain: retrieval's family
rung uses json_extract, and complete_checkpoint's report_version
subquery-in-UPDATE relies on SQLite's single-writer serialization -
revisit both before pointing at another engine.)
SQLite runs in WAL mode with foreign keys enforced. Concurrency: one
short-lived session per operation from a connection pool — no shared
connection, no module-level locks; SQLite's own write serialization is
the only global lock.

All data access is typed: the lifecycle methods below, or module-local
SQLAlchemy queries through `session()` against the models. There is no
raw-SQL escape hatch — add a typed query instead.
"""

from __future__ import annotations

import contextlib
import datetime
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

import json

from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    Checkpoint,
    Decision,
    DossierRevision,
    Episode,
    Feedback,
    Observation,
    Outcome,
    RetrievalAudit,
    Service,
)

__all__ = [
    "Db", "now_iso", "new_id", "row_dict", "to_utc_z",
    "Base", "Service", "Episode", "Checkpoint", "Observation", "Decision",
    "Outcome", "Feedback", "DossierRevision", "RetrievalAudit",
]

log = logging.getLogger("rollout_intel.db")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def to_utc_z(ts: str | None) -> str | None:
    """Normalize an ISO timestamp to UTC 'Z' form. Every stored timestamp
    is already Z (now_iso), but as_of arrives from callers — a +05:30
    offset compared lexicographically against Z strings would silently
    leak future state into replay. Every bitemporal reader normalizes
    through this before comparing."""
    if not ts:
        return ts
    try:
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ts


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _url_for(path_or_url: str) -> str:
    """A bare filesystem path means SQLite; anything with a scheme is a
    SQLAlchemy URL used verbatim."""
    if "://" in path_or_url:
        return path_or_url
    return f"sqlite:///{path_or_url}"


def row_dict(obj: Any) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


class Db:
    def __init__(self, path_or_url: str):
        url = _url_for(path_or_url)
        # A bare filesystem path is snapshot-able (flush); a URL-backed
        # store is not ours to copy around.
        self.path: str | None = None if "://" in path_or_url else path_or_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.close()
        Base.metadata.create_all(self.engine)
        self._patch_legacy_columns()
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False)
        log.info("episode store ready at %s", url)

    # Additive columns introduced after a store format shipped; older
    # DBs are patched in place on open (create_all never alters).
    _LEGACY_PATCHES = (
        ("dossier_journal", "activated_at"),
        ("dossier_journal", "deactivated_at"),
        ("episodes", "external_ref"),
        ("episodes", "event_id"),
        ("decisions", "episode_id"),
    )

    def _patch_legacy_columns(self) -> None:
        with self.engine.connect() as conn:
            for table, col in self._LEGACY_PATCHES:
                try:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                    conn.commit()
                except OperationalError as exc:
                    conn.rollback()
                    msg = str(exc).lower()
                    # Both spellings of the benign duplicate-column case.
                    if ("duplicate column" not in msg
                            and "already exists" not in msg):
                        log.warning("legacy-column patch failed for %s.%s: %s",
                                    table, col, exc)

    def flush(self) -> dict:
        """Quiesce the store for a snapshot upload: close every pooled
        connection, then merge the WAL into the main database file so the
        .db file alone is the complete store. A TRUNCATE checkpoint
        reports busy while pooled readers still hold the file — dispose
        first, checkpoint second. The engine stays usable afterwards
        (connections re-create lazily). URL-backed stores (a central
        Postgres) have nothing to snapshot."""
        self.engine.dispose()
        if self.path is None:
            return {"flushed": False, "reason": "not a file-backed store"}
        import sqlite3
        conn = sqlite3.connect(self.path)
        try:
            busy, wal_pages, moved = conn.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        finally:
            conn.close()
        if busy:
            # Uploading now would silently drop whatever is still in the
            # WAL — refuse instead.
            raise RuntimeError(
                "wal_checkpoint(TRUNCATE) reported busy: another process "
                "still holds this store; close it before snapshotting")
        return {"flushed": True, "wal_pages": wal_pages, "pages_moved": moved}

    @contextlib.contextmanager
    def session(self) -> Iterator[Session]:
        """One transaction: commits on success, rolls back on error."""
        s = self._session_factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # --- services / identity ---------------------------------------------

    def get_service(self, service_uid: str) -> dict | None:
        with self.session() as s:
            service = s.get(Service, service_uid)
            return row_dict(service) if service is not None else None

    def upsert_service(self, svc: dict) -> None:
        # Bounded retry: losing the INSERT race to a concurrent upsert
        # re-enters once and takes the update path.
        for attempt in (0, 1):
            try:
                with self.session() as s:
                    existing = s.get(Service, svc["service_uid"])
                    if existing is not None:
                        # Absent keys preserve the stored value - a sparse fixture
                        # or catalog entry must not blank real metadata.
                        for field in ("runtime", "architecture_version", "owner"):
                            if field in svc:
                                setattr(existing, field, svc[field])
                        if "aliases" in svc:
                            existing.aliases_json = json.dumps(svc["aliases"])
                        return
                    s.add(Service(
                        service_uid=svc["service_uid"], name=svc["name"],
                        environment=svc["environment"], region=svc["region"],
                        runtime=svc.get("runtime", ""),
                        architecture_version=svc.get("architecture_version", ""),
                        owner=svc.get("owner", ""),
                        aliases_json=json.dumps(svc.get("aliases", [])),
                        source=svc.get("source", "catalog"),
                        status=svc.get("status", "confirmed"),
                        created_at=now_iso()))
                return
            except IntegrityError:
                if attempt:
                    raise

    # --- episodes / checkpoints -------------------------------------------

    def create_episode(self, service_uid: str, fingerprint: dict,
                       deploy_event: dict,
                       architecture_version: str | None = None,
                       episode_id: str | None = None) -> dict:
        """architecture_version comes from the caller's fingerprint (the
        event is the truth about the arch change); the service row is only
        the fallback, so a concurrent arch update cannot be lost between
        transactions.

        episode_id may be supplied by the caller when it is DERIVED from a
        trigger's correlation id (deterministic ids make at-least-once
        event delivery idempotent). Losing the insert race on a supplied
        id returns the winner's row — both deliveries land on the same
        episode."""
        supplied = episode_id is not None
        episode_id = episode_id or new_id("ep")
        trigger_info = deploy_event.get("trigger")
        if not isinstance(trigger_info, dict):
            trigger_info = {}
        try:
            with self.session() as s:
                service = s.get(Service, service_uid)
                episode = Episode(
                    episode_id=episode_id, service_uid=service_uid,
                    external_ref=deploy_event.get("external_ref") or None,
                    event_id=trigger_info.get("event_id") or None,
                    revision_from=deploy_event.get("from_revision", ""),
                    revision_to=deploy_event.get("to_revision", ""),
                    fingerprint_json=json.dumps(fingerprint),
                    deploy_event_json=json.dumps(deploy_event),
                    started_at=now_iso(), status="open",
                    architecture_version=(architecture_version
                                          or (service.architecture_version or ""
                                              if service else "")),
                    created_at=now_iso())
                s.add(episode)
                s.flush()
                return row_dict(episode)
        except IntegrityError:
            if not supplied:
                raise  # a random-id collision is a real fault, not a race
            with self.session() as s:
                existing = s.get(Episode, episode_id)
                if existing is None:
                    raise  # not the duplicate-id race (e.g. FK) — surface it
                stored = json.loads(existing.deploy_event_json or "{}")
                if (stored.get("service") and deploy_event.get("service")
                        and stored["service"] != deploy_event["service"]):
                    # Same-ref, different service: an insertId collision,
                    # not a redelivery — never silently adopt it.
                    raise ValueError(
                        f"correlation collision on episode {episode_id}: "
                        f"bound to {stored['service']!r}, this event names "
                        f"{deploy_event['service']!r}")
                result = row_dict(existing)
                # Losing the race IS a duplicate delivery — the caller's
                # pre-insert existence check missed it by milliseconds.
                result["deduplicated"] = True
                return result

    def open_checkpoint(self, episode_id: str, stage: str, session_id: str,
                        scheduled_at: str, refuse_closed: bool = False) -> dict:
        # Idempotent while open: a clock layer that died between session
        # creation and checkpoint registration re-arms the SAME open
        # checkpoint with its new session instead of tripping
        # UNIQUE(episode_id, stage).
        with self.session() as s:
            if refuse_closed:
                # Same transaction as the insert: an outcome label landing
                # between a caller's earlier closed-check and this open
                # cannot slip a checkpoint onto a closed episode. Fixture
                # loading keeps the default (it re-arms labeled corpus
                # episodes deliberately).
                episode = s.get(Episode, episode_id)
                if episode is not None and (
                        episode.final_label is not None
                        or episode.status == "closed"):
                    raise ValueError(f"episode {episode_id} is closed/"
                                     "labeled; no checkpoint may open")
            existing = s.execute(
                select(Checkpoint).where(
                    Checkpoint.episode_id == episode_id,
                    Checkpoint.stage == stage,
                    Checkpoint.completed_at.is_(None))
            ).scalar_one_or_none()
            if existing is not None:
                # Guarded so a concurrent completion is never overwritten:
                # re-arm only while still open; if the guard misses, fall
                # through and return the row as it now stands.
                s.execute(
                    update(Checkpoint)
                    .where(Checkpoint.checkpoint_id == existing.checkpoint_id,
                           Checkpoint.completed_at.is_(None))
                    .values(session_id=session_id, scheduled_at=scheduled_at))
                s.flush()
                s.refresh(existing)
                return row_dict(existing)
            # Episode advance runs before the checkpoint is pending, so
            # autoflush cannot fire the insert early.
            s.execute(
                update(Episode)
                .where(Episode.episode_id == episode_id, Episode.status == "open")
                .values(status="in_progress"))
            checkpoint = Checkpoint(
                checkpoint_id=new_id("cp"), episode_id=episode_id, stage=stage,
                scheduled_at=scheduled_at, session_id=session_id,
                created_at=now_iso())
            try:
                s.add(checkpoint)
                s.flush()
            except IntegrityError:
                # Lost the UNIQUE(episode_id, stage) race to a concurrent
                # opener - adopt their row directly, no recursion.
                s.rollback()
                theirs = s.execute(
                    select(Checkpoint).where(
                        Checkpoint.episode_id == episode_id,
                        Checkpoint.stage == stage)
                ).scalar_one_or_none()
                if theirs is None:
                    raise  # not the unique race (e.g. FK) - surface it
                if theirs.completed_at is None:
                    # Same guarded re-arm as the existing-row path.
                    s.execute(
                        update(Checkpoint)
                        .where(Checkpoint.checkpoint_id == theirs.checkpoint_id,
                               Checkpoint.completed_at.is_(None))
                        .values(session_id=session_id,
                                scheduled_at=scheduled_at))
                    s.flush()
                    s.refresh(theirs)
                # Completed: callers treat the row as "already recorded".
                return row_dict(theirs)
            return row_dict(checkpoint)

    def complete_checkpoint(self, checkpoint_id: str, stage_verdict: str,
                            policy_status: str, policy_version: str,
                            # always False today - conflicted verdicts never
                            # complete a checkpoint; column retained for
                            # schema compatibility
                            policy_conflict: bool, report_md: str,
                            next_check_at: str | None) -> dict | None:
        """Returns None when the checkpoint was already completed — the
        caller lost the race and must not report success or touch the
        episode (lost-update guard from adversarial review)."""
        with self.session() as s:
            checkpoint = s.get(Checkpoint, checkpoint_id)
            if checkpoint is None:
                return None  # unknown id: same contract as the lost race
            episode_id = checkpoint.episode_id
            # report_version is computed atomically inside the guarded
            # UPDATE (scalar subquery), so two concurrent completions on
            # the same episode cannot mint the same version.
            next_version = (
                select(func.coalesce(func.max(Checkpoint.report_version), 0) + 1)
                .where(Checkpoint.episode_id == episode_id)
                .scalar_subquery())
            result = s.execute(
                update(Checkpoint)
                .where(Checkpoint.checkpoint_id == checkpoint_id,
                       Checkpoint.completed_at.is_(None))
                .values(completed_at=now_iso(), stage_verdict=stage_verdict,
                        policy_status=policy_status,
                        policy_version=policy_version,
                        policy_conflict=1 if policy_conflict else 0,
                        report_version=next_version, report_md=report_md,
                        next_check_at=next_check_at))
            if result.rowcount == 0:
                return None
            # The ladder ends when there is no next check — the final
            # ladder stage, the policy's exit criteria, or a governed
            # stabilization window (dynamic scheduling). Closing keys off
            # next_check_at, not stage.
            # final_label guard: a completion that lost the race to a
            # labeling outcome must not reopen a closed episode.
            if next_check_at is None:
                s.execute(
                    update(Episode)
                    .where(Episode.episode_id == episode_id,
                           Episode.final_label.is_(None))
                    .values(status="awaiting_outcome",
                            final_verdict=stage_verdict))
            s.flush()
            s.refresh(checkpoint)
            return row_dict(checkpoint)

    def insert_observation(self, episode_id: str, checkpoint_id: str, env: dict,
                           verified: bool) -> None:
        observation_id = env.get("observation_id", new_id("obs"))
        try:
            with self.session() as s:
                if s.get(Observation, observation_id) is not None:
                    return  # idempotent: same envelope re-presented
                s.add(Observation(
                    observation_id=observation_id, episode_id=episode_id,
                    checkpoint_id=checkpoint_id, type=env.get("type", "unknown"),
                    scope_json=json.dumps(env.get("scope", {})),
                    observed_at=env.get("observed_at"),
                    fresh_until=env.get("fresh_until"), source=env.get("source"),
                    payload_json=json.dumps(env.get("payload")),
                    quality_json=json.dumps(env.get("quality", {})),
                    content_hash=env.get("content_hash"),
                    sig_verified=1 if verified else 0, recorded_at=now_iso()))
        except IntegrityError:
            pass  # concurrent presenter won the race - same envelope

    def insert_decision(self, checkpoint_id: str, kind: str, value: dict,
                        inputs: dict, episode_id: str | None = None) -> None:
        with self.session() as s:
            s.add(Decision(
                decision_id=new_id("dec"), checkpoint_id=checkpoint_id,
                episode_id=episode_id,
                kind=kind, value_json=json.dumps(value),
                inputs_json=json.dumps(inputs), recorded_at=now_iso()))

    def audit_retrieval(self, episode_id: str | None, tool: str, filters: dict,
                        returned_ids: list[str], as_of: str | None) -> None:
        with self.session() as s:
            s.add(RetrievalAudit(
                query_id=new_id("q"), episode_id=episode_id, tool=tool,
                filters_json=json.dumps(filters),
                returned_ids_json=json.dumps(returned_ids), as_of=as_of,
                at=now_iso()))
