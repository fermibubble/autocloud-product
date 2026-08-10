"""SQLAlchemy 2.0 typed models — the single schema definition.

Column names, types, constraints, and defaults are compatible with the
pre-ORM SQLite schema: an episode-store.db created by an older build
opens cleanly under these models (Db patches the additive columns —
episodes.external_ref / episodes.event_id / decisions.episode_id and
the dossier bitemporal pair — in place on open). JSON-carrying columns
stay TEXT (serialized at the repository boundary in db.py) so stored
bytes are identical across the migration.

Design invariants the schema encodes (do not weaken them in a refactor):
  - final_verdict (what the agent concluded) and final_label (what the
    outcome proved) are separate columns; learning joins on final_label
    IS NOT NULL so the agent can never learn from its own verdicts.
  - checkpoints are UNIQUE(episode_id, stage) and complete once.
  - decisions.kind includes 'next_check' (dynamic scheduling audit).
  - outcomes.horizon is free text: the policy pack owns the horizon set.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Service(Base):
    __tablename__ = "services"

    service_uid: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    runtime: Mapped[str | None] = mapped_column(Text)
    architecture_version: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(Text)
    aliases_json: Mapped[str | None] = mapped_column(Text, default="[]",
                                                    server_default="'[]'")
    source: Mapped[str | None] = mapped_column(
        Text, CheckConstraint(
            "source IN ('catalog','labels','platform','inferred')"))
    status: Mapped[str | None] = mapped_column(
        Text, CheckConstraint("status IN ('confirmed','candidate')"),
        default="candidate", server_default="'candidate'")
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Episode(Base):
    __tablename__ = "episodes"

    episode_id: Mapped[str] = mapped_column(Text, primary_key=True)
    # Trigger correlation id (Cloud Logging insertId or synthesized
    # ref) and the birthing delivery's CloudEvents id — first-class so
    # downstream exports stream the table verbatim, no JSON digging.
    external_ref: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[str | None] = mapped_column(Text)
    service_uid: Mapped[str] = mapped_column(
        Text, ForeignKey("services.service_uid"), nullable=False)
    revision_from: Mapped[str | None] = mapped_column(Text)
    revision_to: Mapped[str | None] = mapped_column(Text)
    fingerprint_json: Mapped[str] = mapped_column(Text, nullable=False)
    deploy_event_json: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(
        Text, CheckConstraint(
            "status IN ('open','in_progress','awaiting_outcome','closed')"),
        default="open", server_default="'open'")
    final_verdict: Mapped[str | None] = mapped_column(Text)
    final_label: Mapped[str | None] = mapped_column(Text)
    labeled_at: Mapped[str | None] = mapped_column(Text)
    architecture_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (UniqueConstraint("episode_id", "stage"),)

    checkpoint_id: Mapped[str] = mapped_column(Text, primary_key=True)
    episode_id: Mapped[str] = mapped_column(
        Text, ForeignKey("episodes.episode_id"), nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)
    stage_verdict: Mapped[str | None] = mapped_column(Text)
    policy_status: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[str | None] = mapped_column(Text)
    policy_conflict: Mapped[int | None] = mapped_column(Integer, default=0,
                                                       server_default="0")
    report_version: Mapped[int | None] = mapped_column(Integer)
    report_md: Mapped[str | None] = mapped_column(Text)
    next_check_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Observation(Base):
    __tablename__ = "observations"

    observation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    episode_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_id: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[str | None] = mapped_column(Text)
    fresh_until: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    quality_json: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    sig_verified: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(Text, primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(
        Text, ForeignKey("checkpoints.checkpoint_id"), nullable=False)
    # Denormalized from the checkpoint so per-episode reads (and the
    # BigQuery stream) need no join; the checkpoint remains authoritative.
    episode_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(
        Text, CheckConstraint(
            "kind IN ('stage_verdict','final_verdict','escalation','next_check')"))
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)


class Outcome(Base):
    __tablename__ = "outcomes"

    outcome_id: Mapped[str] = mapped_column(Text, primary_key=True)
    episode_id: Mapped[str] = mapped_column(
        Text, ForeignKey("episodes.episode_id"), nullable=False)
    # Policy-defined (outcome_horizons) + 'final'; deliberately no fixed set.
    horizon: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
    slo_json: Mapped[str | None] = mapped_column(Text)
    rollback_detected: Mapped[int | None] = mapped_column(Integer, default=0,
                                                         server_default="0")
    rollback_at: Mapped[str | None] = mapped_column(Text)
    incident_refs_json: Mapped[str | None] = mapped_column(Text, default="[]",
                                                           server_default="'[]'")
    source: Mapped[str | None] = mapped_column(
        Text, CheckConstraint("source IN ('collector','webhook','human')"))
    notes: Mapped[str | None] = mapped_column(Text)


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(Text, primary_key=True)
    episode_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(
        Text, CheckConstraint(
            "type IN ('human_override','human_confirm','incident_link','root_cause')"))
    actor: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)


class DossierRevision(Base):
    __tablename__ = "dossier_journal"

    rev_id: Mapped[str] = mapped_column(Text, primary_key=True)
    service_uid: Mapped[str] = mapped_column(Text, nullable=False)
    field: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    epistemic_type: Mapped[str | None] = mapped_column(
        Text, CheckConstraint(
            "epistemic_type IN ('approved','observed','asserted','inferred',"
            "'hypothesized','rejected')"))
    status: Mapped[str | None] = mapped_column(
        Text, CheckConstraint(
            "status IN ('proposed','active','superseded','rejected','expired')"))
    confidence: Mapped[float | None] = mapped_column(Float)
    valid_from: Mapped[str | None] = mapped_column(Text)
    valid_to: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(Text)
    sources_json: Mapped[str | None] = mapped_column(Text, default="[]",
                                                    server_default="'[]'")
    rationale: Mapped[str | None] = mapped_column(Text)
    owner_verified_by: Mapped[str | None] = mapped_column(Text)
    superseded_by_rev: Mapped[str | None] = mapped_column(Text)
    memory_id: Mapped[str | None] = mapped_column(Text)
    activated_at: Mapped[str | None] = mapped_column(Text)
    deactivated_at: Mapped[str | None] = mapped_column(Text)


class RetrievalAudit(Base):
    __tablename__ = "retrieval_audit"

    query_id: Mapped[str] = mapped_column(Text, primary_key=True)
    episode_id: Mapped[str | None] = mapped_column(Text)
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    filters_json: Mapped[str | None] = mapped_column(Text)
    returned_ids_json: Mapped[str | None] = mapped_column(Text)
    as_of: Mapped[str | None] = mapped_column(Text)
    at: Mapped[str] = mapped_column(Text, nullable=False)
