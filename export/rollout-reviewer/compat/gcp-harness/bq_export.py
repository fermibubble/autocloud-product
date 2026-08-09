"""bq_export - upload finished rollout episodes from intel.db to BigQuery.

At the end of a rollout review (the ladder ended: final stage, exit
criteria, or a governed window - and later again when the outcome label
lands) the episode store's rows for that episode are appended to a
DEDICATED BigQuery dataset. The existing harness dataset
(autocloud_analysis.agent_executions) is never touched: this module
creates and writes only its own dataset/tables.

Design:
  - Stdlib SQLite reads (no rollout_intel import): the module runs
    anywhere the .db file can be mounted - the Cloud Run event router,
    the agent VM, or a batch job. google-cloud-bigquery is imported
    lazily and only for the actual upload.
  - APPEND-ONLY snapshots: every exported row carries exported_at,
    export_phase ('ladder_complete' | 'outcome_final' | ...), and
    export_session. At-least-once delivery and the two-phase export
    (ladder end, then outcome labeling) produce duplicate snapshots by
    design; analysts read through the *_latest views (see
    LATEST_VIEW_SQL) which keep the newest snapshot per primary key.
    Deterministic per-phase row ids are passed for BigQuery's
    best-effort short-window dedupe.
  - Column names and stored bytes match the SQLite schema exactly
    (…_json columns upload as BigQuery JSON, timestamps as TIMESTAMP);
    the one addition is decisions.episode_id, derived via checkpoints
    so per-episode queries need no join.
  - Scrubbing: pass the harness's DLP hooks - scrub_text(str)->str for
    free-text columns (report_md, notes, rationale, principals),
    scrub_json(obj)->obj for every *_json column. No hooks = no
    scrubbing; the router patch always passes them.
  - Finished-only by default: an episode exports once its ladder ended
    (final_verdict set / status awaiting_outcome|closed). Mid-ladder
    episodes raise LookupError so a router can call this after every
    turn and simply skip the not-finished case. force=True overrides.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
from typing import Any, Callable

DEFAULT_DATASET = "autocloud_rollout_intel"

_FINISHED_SQL = ("final_verdict IS NOT NULL "
                 "OR status IN ('awaiting_outcome', 'closed')")

# table -> (primary key, ordered columns). Columns mirror
# rollout_intel/models.py byte-for-byte; keep the twins in sync.
_TABLES: dict[str, tuple[str, list[str]]] = {
    "services": ("service_uid", [
        "service_uid", "name", "environment", "region", "runtime",
        "architecture_version", "owner", "aliases_json", "source", "status",
        "confirmed_by", "confirmed_at", "created_at"]),
    "episodes": ("episode_id", [
        "episode_id", "service_uid", "revision_from", "revision_to",
        "fingerprint_json", "deploy_event_json", "started_at", "status",
        "final_verdict", "final_label", "labeled_at", "architecture_version",
        "created_at"]),
    "checkpoints": ("checkpoint_id", [
        "checkpoint_id", "episode_id", "stage", "scheduled_at", "session_id",
        "completed_at", "stage_verdict", "policy_status", "policy_version",
        "policy_conflict", "report_version", "report_md", "next_check_at",
        "created_at"]),
    "observations": ("observation_id", [
        "observation_id", "episode_id", "checkpoint_id", "type", "scope_json",
        "observed_at", "fresh_until", "source", "payload_json", "quality_json",
        "content_hash", "sig_verified", "recorded_at"]),
    "decisions": ("decision_id", [
        "decision_id", "checkpoint_id", "episode_id", "kind", "value_json",
        "inputs_json", "recorded_at"]),
    "outcomes": ("outcome_id", [
        "outcome_id", "episode_id", "horizon", "collected_at", "slo_json",
        "rollback_detected", "rollback_at", "incident_refs_json", "source",
        "notes"]),
    "feedback": ("feedback_id", [
        "feedback_id", "episode_id", "type", "actor", "payload_json",
        "recorded_at"]),
    "dossier_journal": ("rev_id", [
        "rev_id", "service_uid", "field", "value_json", "epistemic_type",
        "status", "confidence", "valid_from", "valid_to", "recorded_at",
        "expires_at", "sources_json", "rationale", "owner_verified_by",
        "superseded_by_rev", "memory_id", "activated_at", "deactivated_at"]),
    "retrieval_audit": ("query_id", [
        "query_id", "episode_id", "tool", "filters_json",
        "returned_ids_json", "as_of", "at"]),
}

_BQ_TABLE_PREFIX = "rollout_"

_TIMESTAMP_COLS = {
    "confirmed_at", "created_at", "started_at", "labeled_at", "scheduled_at",
    "completed_at", "observed_at", "fresh_until", "recorded_at",
    "collected_at", "rollback_at", "valid_from", "valid_to", "expires_at",
    "activated_at", "deactivated_at", "as_of", "at", "exported_at",
}
_INT_COLS = {"policy_conflict", "report_version", "sig_verified",
             "rollback_detected"}
_FLOAT_COLS = {"confidence"}
# Free-text columns the scrub_text hook covers (…_json columns are
# covered by scrub_json wholesale).
_SCRUB_TEXT_COLS = {"report_md", "notes", "rationale", "actor", "owner",
                    "confirmed_by", "owner_verified_by"}

_EXPORT_COLS = ["exported_at", "export_phase", "export_session"]

LATEST_VIEW_SQL = """-- One view per table: the newest snapshot per primary key.
CREATE OR REPLACE VIEW `{project}.{dataset}.{table}_latest` AS
SELECT * EXCEPT (rn) FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY {pk} ORDER BY exported_at DESC) AS rn
  FROM `{project}.{dataset}.{table}`)
WHERE rn = 1;
"""


def episode_id_for_ref(ref: str) -> str:
    """Twin of rollout_intel.service.episode_id_for_ref - keep in sync."""
    return f"ep_{hashlib.sha256(ref.encode()).hexdigest()[:16]}"


def _bq_type(col: str) -> str:
    if col in _TIMESTAMP_COLS:
        return "TIMESTAMP"
    if col in _INT_COLS:
        return "INT64"
    if col in _FLOAT_COLS:
        return "FLOAT64"
    if col.endswith("_json"):
        return "JSON"
    return "STRING"


def bq_schema(table: str) -> list[dict]:
    """Column schema for one exported table, as plain dicts (the shape
    bigquery.SchemaField.from_api_repr and table creation accept)."""
    pk, cols = _TABLES[table]
    fields = []
    for col in cols + _EXPORT_COLS:
        fields.append({
            "name": col,
            "type": _bq_type(col),
            "mode": ("REQUIRED" if col in (pk, "exported_at") else "NULLABLE"),
        })
    return fields


def _ts(value):
    """ISO-Z strings pass through for TIMESTAMP columns; anything
    unparseable becomes NULL rather than failing the row."""
    if value in (None, ""):
        return None
    try:
        datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return value
    except ValueError:
        return None


def _connect(db_path: str) -> sqlite3.Connection:
    # Read-only URI: the exporter must never create or mutate a store.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def find_finished_episodes(db_path: str) -> list[str]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT episode_id FROM episodes WHERE {_FINISHED_SQL} "
            "ORDER BY created_at, episode_id").fetchall()
    return [r["episode_id"] for r in rows]


def collect_episode_rows(db_path: str, episode_id: str, *,
                         force: bool = False) -> dict[str, list[dict]]:
    """All rows belonging to one episode, keyed by (sqlite) table name.

    Raises LookupError when the episode is unknown, or (unless force)
    when its ladder has not ended - callers invoke this after every
    turn and skip the mid-ladder case.
    """
    with _connect(db_path) as conn:
        episode = conn.execute(
            "SELECT * FROM episodes WHERE episode_id = ?",
            (episode_id,)).fetchone()
        if episode is None:
            raise LookupError(f"unknown episode {episode_id!r}")
        finished = conn.execute(
            f"SELECT 1 FROM episodes WHERE episode_id = ? AND ({_FINISHED_SQL})",
            (episode_id,)).fetchone() is not None
        if not (finished or force):
            raise LookupError(
                f"episode {episode_id} has not finished its ladder yet "
                "(no final verdict); pass force=True to export anyway")

        def rows(sql, *args):
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

        out = {
            "episodes": [dict(episode)],
            "services": rows("SELECT * FROM services WHERE service_uid = ?",
                             episode["service_uid"]),
            "checkpoints": rows(
                "SELECT * FROM checkpoints WHERE episode_id = ? "
                "ORDER BY created_at, checkpoint_id", episode_id),
            # episode_id is derived onto decisions so per-episode BQ
            # queries need no join.
            "decisions": rows(
                "SELECT d.*, c.episode_id AS episode_id FROM decisions d "
                "JOIN checkpoints c ON c.checkpoint_id = d.checkpoint_id "
                "WHERE c.episode_id = ? ORDER BY d.recorded_at, d.decision_id",
                episode_id),
            "observations": rows(
                "SELECT * FROM observations WHERE episode_id = ? "
                "ORDER BY recorded_at, observation_id", episode_id),
            "outcomes": rows(
                "SELECT * FROM outcomes WHERE episode_id = ? "
                "ORDER BY collected_at, outcome_id", episode_id),
            "feedback": rows(
                "SELECT * FROM feedback WHERE episode_id = ? "
                "ORDER BY recorded_at, feedback_id", episode_id),
            "dossier_journal": rows(
                "SELECT * FROM dossier_journal WHERE service_uid = ? "
                "ORDER BY recorded_at, rev_id", episode["service_uid"]),
            "retrieval_audit": rows(
                "SELECT * FROM retrieval_audit WHERE episode_id = ? "
                "ORDER BY at, query_id", episode_id),
        }
    return out


def _prepare(table: str, raw: dict, exported_at: str, phase: str,
             export_session: str,
             scrub_text: Callable[[str], str] | None,
             scrub_json: Callable[[Any], Any] | None) -> dict:
    _, cols = _TABLES[table]
    row: dict[str, Any] = {}
    for col in cols:
        value = raw.get(col)
        if value is not None and col in _SCRUB_TEXT_COLS and scrub_text:
            value = scrub_text(str(value))
        if col.endswith("_json"):
            if value is not None and scrub_json is not None:
                try:
                    value = json.dumps(scrub_json(json.loads(value)))
                except ValueError:
                    # Recorder-never-gates means a stored payload is not
                    # guaranteed parseable; scrub it as plain text.
                    value = scrub_text(str(value)) if scrub_text else value
            # JSON columns take a JSON-formatted string verbatim.
        elif col in _TIMESTAMP_COLS:
            value = _ts(value)
        row[col] = value
    row["exported_at"] = exported_at
    row["export_phase"] = phase
    row["export_session"] = export_session
    return row


def ensure_dataset_and_tables(client, project: str,
                              dataset: str = DEFAULT_DATASET,
                              location: str = "US") -> None:
    """Idempotently create the dedicated dataset and its tables. Existing
    datasets/tables are left exactly as they are - this module never
    alters anything pre-existing."""
    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound

    dataset_ref = bigquery.Dataset(f"{project}.{dataset}")
    dataset_ref.location = location
    try:
        client.get_dataset(f"{project}.{dataset}")
    except NotFound:
        client.create_dataset(dataset_ref, exists_ok=True)
    for table in _TABLES:
        table_id = f"{project}.{dataset}.{_BQ_TABLE_PREFIX}{table}"
        try:
            client.get_table(table_id)
        except NotFound:
            schema = [bigquery.SchemaField.from_api_repr(f)
                      for f in bq_schema(table)]
            bq_table = bigquery.Table(table_id, schema=schema)
            bq_table.time_partitioning = bigquery.TimePartitioning(
                field="exported_at")
            client.create_table(bq_table, exists_ok=True)


def export_episode(db_path: str, *, phase: str,
                   episode_id: str | None = None,
                   external_ref: str | None = None,
                   project: str | None = None,
                   dataset: str = DEFAULT_DATASET,
                   client=None,
                   export_session: str = "",
                   scrub_text: Callable[[str], str] | None = None,
                   scrub_json: Callable[[Any], Any] | None = None,
                   ensure_schema: bool = True,
                   force: bool = False,
                   location: str = "US") -> dict:
    """Append one finished episode's rows to the dedicated dataset.

    Identify the episode by id or by the trigger correlation ref
    (insertId / deferred unique_id). Returns {table: row_count}.
    Raises LookupError for unknown/not-finished episodes (callers skip
    the latter), RuntimeError when BigQuery rejects rows.
    """
    if episode_id is None:
        if not external_ref:
            raise ValueError("pass episode_id or external_ref")
        episode_id = episode_id_for_ref(external_ref)
    collected = collect_episode_rows(db_path, episode_id, force=force)

    if client is None:
        from google.cloud import bigquery
        client = bigquery.Client(project=project)
    project = project or client.project
    if ensure_schema:
        ensure_dataset_and_tables(client, project, dataset, location)

    exported_at = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary: dict[str, int] = {}
    failures: list[str] = []
    for table, raw_rows in collected.items():
        if not raw_rows:
            continue
        pk, _ = _TABLES[table]
        rows = [_prepare(table, r, exported_at, phase, export_session,
                         scrub_text, scrub_json) for r in raw_rows]
        # Deterministic per-phase ids: BigQuery's short-window best-effort
        # dedupe absorbs immediate Cloud Tasks retries; the *_latest
        # views handle everything beyond the window.
        row_ids = [f"{phase}:{r[pk]}" for r in rows]
        table_id = f"{project}.{dataset}.{_BQ_TABLE_PREFIX}{table}"
        errors = client.insert_rows_json(table_id, rows, row_ids=row_ids)
        if errors:
            failures.append(f"{table_id}: {errors}")
        else:
            summary[table] = len(rows)
    if failures:
        raise RuntimeError("BigQuery rejected rows: " + "; ".join(failures))
    return summary
