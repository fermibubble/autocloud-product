"""DDL artifacts for the rollout-intel BigQuery export.

Deliberately separate from the exporter: bq_export.py only STREAMS
rows; everything that describes or creates tables and views lives here
and runs out of band. The table/column data model (names, primary
keys, type classes) stays in bq_export.py - this module imports it, so
the schema files, the views, and the streamed rows can never disagree
(a parity test additionally pins the committed *.schema.json files to
this generator).

Commands:
  python3 generate_ddl.py emit-schemas [OUTDIR]
      (Re)generate the committed rollout_*.schema.json files (the
      `bq mk --schema` format) - run after any data-model change, then
      commit and re-run setup-bq.sh / `bq update --schema`.
  python3 generate_ddl.py emit-views PROJECT [DATASET]
      Print the *_latest CREATE OR REPLACE VIEW statements
      (setup-views.sh pipes them into `bq query`).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "bq_export_data_model",
    Path(__file__).resolve().parent.parent / "bq_export.py")
bq_export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bq_export)

# Column documentation, emitted into the *.schema.json files and the
# created tables. Keyed "table.column" for table-specific text, bare
# "column" for columns shared across tables.
_DESCRIPTIONS = {
    "exported_at": "Snapshot upload time (microsecond precision); the "
                   "*_latest views key on it",
    "export_phase": "ladder_complete (final verdict recorded) | "
                    "outcome_final (re-export after ground-truth labeling)",
    "export_session": "Harness session that ran the export",
    "episode_id": "Episode this row belongs to; ep_<sha256(ref)[:16]> "
                  "for trigger-born episodes",
    "service_uid": "Canonical identity svc://tenant/name/env/region; "
                   "inferred*/ tenants are runtime candidates",
    "services.status": "confirmed (catalog-backed) | candidate (inferred)",
    "episodes.episode_id": "Primary key; deterministic ep_<sha256("
                           "external_ref)[:16]> for trigger-born episodes",
    "episodes.external_ref": "Trigger correlation id: the Cloud Logging "
                             "insertId (or synth-<hash> for insertId-less "
                             "entries). Equals defer_verification's "
                             "unique_id and agent_executions.insert_id - "
                             "THE join key to the harness table. Stamped "
                             "on the episode row at creation",
    "episodes.event_id": "CloudEvents id of the TRIGGERING delivery, when "
                         "the forwarded event carried a top-level 'id'. "
                         "Per-delivery, not per-episode: each deferred fire "
                         "gets a fresh ce-id - find those in "
                         "agent_executions via session_id / insert_id",
    "episodes.fingerprint_json": "Deterministic rollout fingerprint - the "
                                 "retrieval key for precedent matching",
    "episodes.deploy_event_json": "Parsed deploy event incl. external_ref "
                                  "and trigger provenance (DLP-scrubbed)",
    "episodes.status": "open | in_progress | awaiting_outcome | closed",
    "episodes.final_verdict": "What the agent concluded: healthy | "
                              "regression-suspected | insufficient-evidence",
    "episodes.final_label": "What reality proved: healthy | regressed | "
                            "rolled_back - from outcomes/humans, never from "
                            "agent verdicts",
    "checkpoints.stage": "Policy ladder stage name (policy pack owned)",
    "checkpoints.session_id": "Harness session that most recently armed "
                              "this checkpoint - normally the one that "
                              "recorded it; a crash re-fire overwrites it "
                              "with the new session. Joins "
                              "agent_executions.session_id",
    "checkpoints.stage_verdict": "healthy | regression-suspected | "
                                 "insufficient-evidence",
    "checkpoints.policy_status": "Deterministic policy result: pass | fail "
                                 "| insufficient_evidence",
    "checkpoints.report_md": "Full stage report embedding the epistemic "
                             "record (DLP-scrubbed)",
    "checkpoints.next_check_at": "Human-readable schedule decision label "
                                 "('+Nm', policy vocabulary); "
                                 "next_check_delay_seconds is the numeric "
                                 "companion. Both NULL = the ladder ended",
    "checkpoints.next_check_delay_seconds": "The decided delay in seconds "
                                            "- exactly what "
                                            "defer_verification was armed "
                                            "with. Due time = "
                                            "TIMESTAMP_ADD(completed_at, "
                                            "INTERVAL "
                                            "next_check_delay_seconds "
                                            "SECOND). NULL = ladder ended",
    "checkpoints.report_version": "Monotonic per-episode report version",
    "observations.sig_verified": "1 = HMAC evidence-envelope signature "
                                 "verified at recording time",
    "observations.payload_json": "Observation payload (DLP-scrubbed); may "
                                 "be a JSON string literal when the stored "
                                 "bytes were not parseable",
    "decisions.kind": "stage_verdict | final_verdict | escalation | "
                      "next_check",
    "decisions.episode_id": "Denormalized from the checkpoint at decision "
                            "time so per-episode queries need no join "
                            "(NULL on rows written before the column "
                            "existed; the checkpoint join is authoritative)",
    "outcomes.horizon": "Policy outcome horizon (e.g. 30m/2h/24h) or "
                        "'final'",
    "outcomes.source": "collector | webhook | human",
    "feedback.type": "human_override | human_confirm | incident_link | "
                     "root_cause",
    "dossier_journal.epistemic_type": "approved | observed | asserted | "
                                      "inferred | hypothesized | rejected",
    "dossier_journal.status": "proposed | active | superseded | rejected "
                              "| expired",
    "retrieval_audit.as_of": "Bitemporal read point of the retrieval",
}

LATEST_VIEW_SQL = """-- One view per table: the newest snapshot per primary key.
-- Tiebreakers: outcome_final outranks ladder_complete at equal
-- timestamps; export_session makes the order fully deterministic.
CREATE OR REPLACE VIEW `{project}.{dataset}.{table}_latest` AS
SELECT * EXCEPT (rn) FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY {pk}
    ORDER BY exported_at DESC,
             IF(export_phase = 'outcome_final', 1, 0) DESC,
             export_session DESC) AS rn
  FROM `{project}.{dataset}.{table}`)
WHERE rn = 1;
"""


def _bq_type(col: str) -> str:
    # Legacy type names (INTEGER/FLOAT) deliberately: the conventional
    # vocabulary of `bq mk --schema` files, and what the API echoes
    # back for live tables.
    if col in bq_export._TIMESTAMP_COLS:
        return "TIMESTAMP"
    if col in bq_export._INT_COLS:
        return "INTEGER"
    if col in bq_export._FLOAT_COLS:
        return "FLOAT"
    if col.endswith("_json"):
        return "JSON"
    return "STRING"


def bq_schema(table: str) -> list[dict]:
    """Column schema for one exported table - the exact shape of a
    `bq mk --schema` JSON file entry."""
    pk, cols = bq_export._TABLES[table]
    fields = []
    for col in cols + bq_export._EXPORT_COLS:
        field = {
            "name": col,
            "type": _bq_type(col),
            "mode": ("REQUIRED" if col in (pk, "exported_at") else "NULLABLE"),
        }
        description = _DESCRIPTIONS.get(f"{table}.{col}") or \
            _DESCRIPTIONS.get(col)
        if description:
            field["description"] = description
        fields.append(field)
    return fields


def emit_schema_files(outdir: str | None = None) -> list[str]:
    """Write one `bq mk --schema` JSON file per table (defaults to this
    directory). Returns the written paths."""
    outdir = outdir or str(Path(__file__).resolve().parent)
    os.makedirs(outdir, exist_ok=True)
    written = []
    for table in bq_export._TABLES:
        path = os.path.join(
            outdir, f"{bq_export._BQ_TABLE_PREFIX}{table}.schema.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bq_schema(table), f, indent=2)
            f.write("\n")
        written.append(path)
    return written


def emit_views_sql(project: str, dataset: str | None = None) -> str:
    """The *_latest view DDL for every table, as one multi-statement
    script (pipe into `bq query --use_legacy_sql=false`)."""
    dataset = dataset or bq_export.DEFAULT_DATASET
    return "\n".join(
        LATEST_VIEW_SQL.format(project=project, dataset=dataset,
                               table=f"{bq_export._BQ_TABLE_PREFIX}{table}",
                               pk=pk)
        for table, (pk, _) in bq_export._TABLES.items())


if __name__ == "__main__":
    usage = ("usage: generate_ddl.py emit-schemas [OUTDIR] | "
             "emit-views PROJECT [DATASET]")
    if len(sys.argv) >= 2 and sys.argv[1] == "emit-schemas":
        for written_path in emit_schema_files(
                sys.argv[2] if len(sys.argv) > 2 else None):
            print(written_path)
    elif len(sys.argv) >= 3 and sys.argv[1] == "emit-views":
        print(emit_views_sql(sys.argv[2], *(sys.argv[3:4] or ())))
    else:
        print(usage, file=sys.stderr)
        raise SystemExit(2)
