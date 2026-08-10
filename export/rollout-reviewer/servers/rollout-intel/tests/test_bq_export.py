"""bq_export: the BigQuery episode exporter (compat/gcp-harness).

Runs entirely without google-cloud-bigquery: collection and row
preparation are exercised against a real store built through Intel
(begin_review -> record x3 -> outcome label), and the upload path is
driven with a fake client capturing insert_rows_json calls
(the module performs no DDL, so a fake client suffices).
"""

import importlib.util
import time
from pathlib import Path

import pytest
import yaml

import rollout_intel.service as service_module
from rollout_intel.models import Episode, Outcome
from rollout_intel.db import now_iso
from rollout_intel.service import Intel, episode_id_for_ref

_spec = importlib.util.spec_from_file_location(
    "bq_export_under_test",
    Path(__file__).resolve().parents[3] / "compat" / "gcp-harness"
    / "bq_export.py")
bq_export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bq_export)

CATALOG = {"services": [
    {"tenant": "autocloud", "name": "checkout", "environment": "prod",
     "region": "us-east1", "runtime": "cloud-run",
     "architecture_version": "v1", "owner": "team-payments"}]}

POLICY = {
    "name": "bq-pack", "version": 1,
    "rules": [{"id": "wl", "type": "workload_serving", "stages": ["B+0"]}],
    "checkpoints": {
        "ladder": [{"stage": "B+0", "offset_minutes": 0},
                   {"stage": "B+10", "offset_minutes": 10}],
        "bounds": {"min_interval_minutes": 2, "max_interval_minutes": 60},
    },
}

EVENT = {
    "insertId": "bq-export-trigger-1",
    "id": "ce-delivery-42",  # CloudEvents structured-mode id
    "logName": "projects/p/logs/cloudaudit.googleapis.com%2Factivity",
    "protoPayload": {"methodName": "io.k8s.apps.v1.deployments.update",
                     "serviceName": "k8s.io",
                     "resourceName": "apps/v1/namespaces/ns/deployments/shop",
                     "request": {"spec": {"template": {"spec": {"containers": [
                         {"name": "shop", "image": "gcr.io/x/shop@sha256:1"}]}}}}},
    "resource": {"labels": {"cluster_name": "c1", "location": "us-central1",
                            "project_id": "p"}},
    "timestamp": "2026-08-09T03:00:00Z",
}


@pytest.fixture
def finished_store(tmp_path, monkeypatch):
    """A store holding one FINISHED episode (ladder ended, outcome
    labeled) plus dossier/retrieval history. Returns (db_path, episode_id)."""
    monkeypatch.delenv("ENSEMBLE_TOKEN", raising=False)
    policy = tmp_path / "policy.yaml"
    policy.write_text(yaml.safe_dump(POLICY), encoding="utf-8")
    catalog = tmp_path / "services.yaml"
    catalog.write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    db_path = str(tmp_path / "intel.db")
    intel = Intel(db_path, str(policy), str(catalog))

    out = intel.begin_review(EVENT, "sess-1")
    episode_id = out["episode_id"]
    intel.context_pack(episode_id)  # journals a retrieval_audit row
    r1 = intel.record(episode_id, "B+0", [], "insufficient-evidence",
                      "reasoning", "# report SENSITIVE-0", [], [])
    assert r1["next_check_at"] is not None
    shifted = time.time() + 11 * 60
    monkeypatch.setattr(
        service_module, "now_iso",
        lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(shifted)))
    intel.begin_review({"type": "deferred_check",
                        "unique_id": EVENT["insertId"]}, "sess-2")
    r2 = intel.record(episode_id, "B+10", [], "insufficient-evidence",
                      "reasoning", "# report SENSITIVE-1", [], [])
    assert r2["next_check_at"] is None  # ladder ended
    with intel.db.session() as s:
        s.add(Outcome(outcome_id=f"out_{episode_id}_final",
                      episode_id=episode_id, horizon="final",
                      collected_at=now_iso(), slo_json="{}",
                      rollback_detected=0, incident_refs_json="[]",
                      source="collector", notes="clean SENSITIVE-2"))
        episode = s.get(Episode, episode_id)
        episode.final_label = "healthy"
        episode.labeled_at = now_iso()
        episode.status = "closed"
    intel.db.flush()
    return db_path, episode_id


def test_schema_covers_every_collected_column(finished_store):
    db_path, episode_id = finished_store
    collected = bq_export.collect_episode_rows(db_path, episode_id)
    for table, rows in collected.items():
        schema_cols = {f["name"] for f in bq_export.bq_schema(table)}
        for row in rows:
            missing = set(row) - schema_cols
            assert not missing, f"{table}: columns {missing} not in schema"
        pk, _ = bq_export._TABLES[table]
        by_name = {f["name"]: f for f in bq_export.bq_schema(table)}
        assert by_name[pk]["mode"] == "REQUIRED"
        assert by_name["exported_at"]["type"] == "TIMESTAMP"
        for f in bq_export.bq_schema(table):
            if f["name"].endswith("_json"):
                assert f["type"] == "JSON"


def test_collect_gathers_the_full_episode(finished_store):
    db_path, episode_id = finished_store
    collected = bq_export.collect_episode_rows(db_path, episode_id)
    assert len(collected["episodes"]) == 1
    assert collected["episodes"][0]["final_label"] == "healthy"
    # The derived join keys: insertId to agent_executions.insert_id,
    # and the triggering delivery's CloudEvents id.
    assert collected["episodes"][0]["external_ref"] == EVENT["insertId"]
    assert collected["episodes"][0]["event_id"] == "ce-delivery-42"
    assert len(collected["checkpoints"]) == 2
    assert len(collected["outcomes"]) == 1
    # stage_verdict + next_check decisions per checkpoint.
    assert len(collected["decisions"]) == 4
    assert all(d["episode_id"] == episode_id for d in collected["decisions"])
    assert len(collected["services"]) == 1
    assert collected["retrieval_audit"]  # context-pack reads are journaled


def test_unfinished_episode_is_skippable_not_exportable(tmp_path, monkeypatch):
    monkeypatch.delenv("ENSEMBLE_TOKEN", raising=False)
    policy = tmp_path / "p.yaml"
    policy.write_text(yaml.safe_dump(POLICY), encoding="utf-8")
    catalog = tmp_path / "c.yaml"
    catalog.write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    db_path = str(tmp_path / "mid.db")
    intel = Intel(db_path, str(policy), str(catalog))
    out = intel.begin_review(EVENT, "sess-1")  # mid-ladder: B+0 open
    intel.db.flush()
    # Distinct exception types: mid-ladder is the normal skip, an
    # unknown ref is NOT (both remain LookupErrors for back-compat).
    with pytest.raises(bq_export.NotFinishedError, match="not finished"):
        bq_export.collect_episode_rows(db_path, out["episode_id"])
    forced = bq_export.collect_episode_rows(db_path, out["episode_id"],
                                            force=True)
    assert len(forced["episodes"]) == 1
    with pytest.raises(bq_export.UnknownEpisodeError, match="unknown episode"):
        bq_export.collect_episode_rows(db_path, "ep_nope")
    assert issubclass(bq_export.NotFinishedError, LookupError)
    assert issubclass(bq_export.UnknownEpisodeError, LookupError)


def test_external_ref_twin_matches_service_side(finished_store):
    db_path, episode_id = finished_store
    assert bq_export.episode_id_for_ref(EVENT["insertId"]) == \
        episode_id_for_ref(EVENT["insertId"]) == episode_id


class FakeBq:
    def __init__(self):
        self.project = "test-proj"
        self.calls = []

    def insert_rows_json(self, table_id, rows, row_ids=None):
        self.calls.append((table_id, rows, row_ids))
        return []


def test_export_uploads_scrubbed_snapshot_rows(finished_store):
    db_path, _ = finished_store
    fake = FakeBq()
    summary = bq_export.export_episode(
        db_path, phase="ladder_complete",
        external_ref=EVENT["insertId"],
        client=fake, export_session="sess-2",
        scrub_text=lambda s: s.replace("SENSITIVE", "[RED]"),
        scrub_json=lambda obj: obj)
    assert summary["episodes"] == 1 and summary["checkpoints"] == 2
    by_table = {t.split(".")[-1]: (rows, ids) for t, rows, ids in fake.calls}
    assert set(by_table) == {f"rollout_{t}" for t in summary}
    # The episodes commit marker is inserted LAST.
    assert fake.calls[-1][0].endswith(".rollout_episodes")
    checkpoint_rows, checkpoint_ids = by_table["rollout_checkpoints"]
    assert all("[RED]" in r["report_md"] and "SENSITIVE" not in r["report_md"]
               for r in checkpoint_rows)
    assert all(r["export_phase"] == "ladder_complete"
               and r["export_session"] == "sess-2"
               and "." in r["exported_at"]  # microsecond precision
               for r in checkpoint_rows)
    # Content-hashed row ids: phase:pk:digest.
    for row, row_id in zip(checkpoint_rows, checkpoint_ids):
        prefix = f"ladder_complete:{row['checkpoint_id']}:"
        assert row_id.startswith(prefix)
        assert len(row_id) == len(prefix) + 12
    outcome_rows, _ = by_table["rollout_outcomes"]
    assert "[RED]" in outcome_rows[0]["notes"]
    # JSON columns stay JSON-formatted strings.
    episode_rows, _ = by_table["rollout_episodes"]
    assert episode_rows[0]["external_ref"] == EVENT["insertId"]
    import json as _json
    assert _json.loads(episode_rows[0]["deploy_event_json"])["service"] == "shop"


def test_export_raises_on_bq_row_errors(finished_store):
    db_path, _ = finished_store

    class Rejecting(FakeBq):
        def insert_rows_json(self, table_id, rows, row_ids=None):
            return [{"index": 0, "errors": [{"reason": "invalid"}]}]

    with pytest.raises(RuntimeError, match="rejected"):
        bq_export.export_episode(db_path, phase="ladder_complete",
                                 external_ref=EVENT["insertId"],
                                 client=Rejecting())


def test_timestamp_sanitizer_and_finished_finder(finished_store):
    db_path, episode_id = finished_store
    assert bq_export._ts("2026-08-09T03:00:00Z") == "2026-08-09T03:00:00Z"
    assert bq_export._ts("+30m") is None  # next_check_at is NOT a timestamp
    assert bq_export._ts(None) is None
    assert "next_check_at" not in bq_export._TIMESTAMP_COLS
    assert bq_export.find_finished_episodes(db_path) == [episode_id]
    # Phase filters: this episode is labeled, so it belongs to the
    # outcome_final phase, not a ladder_complete fallback sweep.
    assert bq_export.find_finished_episodes(
        db_path, for_phase="ladder_complete") == []
    assert bq_export.find_finished_episodes(
        db_path, for_phase="outcome_final") == [episode_id]


def test_unparseable_stored_json_exports_as_string_literal(finished_store):
    """Recorder-never-gates: bytes that are not valid JSON must become a
    JSON string literal (always valid for a JSON column), scrubbed,
    counted — never a poison pill that rejects the table forever."""
    import sqlite3 as _sqlite3
    db_path, episode_id = finished_store
    conn = _sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO observations (observation_id, episode_id, type, "
            "payload_json, sig_verified, recorded_at) VALUES "
            "('obs_bad', ?, 'log_scan', '{not valid SENSITIVE json', 0, "
            "'2026-08-09T03:05:00Z')", (episode_id,))
        conn.commit()
    finally:
        conn.close()
    fake = FakeBq()
    summary = bq_export.export_episode(
        db_path, phase="outcome_final", episode_id=episode_id,
        client=fake,
        scrub_text=lambda s: s.replace("SENSITIVE", "[RED]"),
        scrub_json=lambda obj: obj)
    assert summary["unparseable_json"] == 1
    rows = next(r for t, r, _ in fake.calls if t.endswith("_observations"))
    bad = next(r for r in rows if r["observation_id"] == "obs_bad")
    import json as _json
    literal = _json.loads(bad["payload_json"])  # valid JSON: a string
    assert isinstance(literal, str)
    assert "[RED]" in literal and "SENSITIVE" not in literal


def test_scrub_json_failure_fails_closed_to_null(finished_store):
    db_path, episode_id = finished_store

    def exploding(obj):
        raise TypeError("DLP hook broke")

    fake = FakeBq()
    summary = bq_export.export_episode(
        db_path, phase="outcome_final", episode_id=episode_id,
        client=fake,
        scrub_text=lambda s: s, scrub_json=exploding)
    assert summary["scrub_failures"] > 0
    episode_rows = next(r for t, r, _ in fake.calls
                        if t.endswith("_episodes"))
    # Never exported unscrubbed: the structural value became NULL.
    assert episode_rows[0]["deploy_event_json"] is None


def test_one_sided_scrub_hooks_are_rejected(finished_store):
    db_path, episode_id = finished_store
    with pytest.raises(ValueError, match="BOTH"):
        bq_export.export_episode(db_path, phase="x", episode_id=episode_id,
                                 client=FakeBq(),
                                 scrub_text=lambda s: s)


def test_denylisted_dataset_is_refused_before_any_work(finished_store):
    db_path, episode_id = finished_store
    with pytest.raises(ValueError, match="harness dataset"):
        bq_export.export_episode(db_path, phase="x", episode_id=episode_id,
                                 dataset="autocloud_analysis",
                                 client=FakeBq())


def test_immutable_read_creates_no_sqlite_side_files(finished_store):
    db_path, episode_id = finished_store
    wal, shm = Path(db_path + "-wal"), Path(db_path + "-shm")
    for leftover in (wal, shm):
        if leftover.exists():
            leftover.unlink()
    bq_export.collect_episode_rows(db_path, episode_id)
    assert not wal.exists() and not shm.exists()


def test_committed_schema_files_match_the_module():
    """The bq/*.schema.json files are the out-of-band DDL source; this
    parity test pins them to bq_schema() so the exporter's row shapes
    and the `bq mk` tables can never drift apart. On failure:
    `python3 compat/gcp-harness/bq_export.py emit-schemas` and re-run
    bq/setup-bq.sh."""
    import json as _json
    bq_dir = Path(_spec.origin).parent / "bq"
    expected_files = {f"rollout_{t}.schema.json" for t in bq_export._TABLES}
    actual_files = {p.name for p in bq_dir.glob("rollout_*.schema.json")}
    assert actual_files == expected_files
    for table in bq_export._TABLES:
        committed = _json.loads(
            (bq_dir / f"rollout_{table}.schema.json").read_text())
        assert committed == bq_export.bq_schema(table), \
            f"{table}: regenerate with `bq_export.py emit-schemas`"
    # The setup script exists alongside them.
    assert (bq_dir / "setup-bq.sh").exists()


def test_emit_views_and_no_runtime_ddl(finished_store, tmp_path):
    sql = bq_export.emit_views_sql("proj-x", "ds-y")
    assert sql.count("CREATE OR REPLACE VIEW") == len(bq_export._TABLES)
    assert "`proj-x.ds-y.rollout_episodes_latest`" in sql
    # emit_schema_files round-trips.
    written = bq_export.emit_schema_files(str(tmp_path / "out"))
    assert len(written) == len(bq_export._TABLES)
    # The module performs NO runtime DDL: no creation entry points, and
    # a bare export streams straight through a client that only knows
    # insert_rows_json (any DDL attempt would AttributeError on FakeBq).
    assert not hasattr(bq_export, "ensure_dataset_and_tables")
    db_path, episode_id = finished_store
    summary = bq_export.export_episode(db_path, phase="outcome_final",
                                       episode_id=episode_id,
                                       client=FakeBq())
    assert summary["episodes"] == 1


def test_missing_table_names_the_out_of_band_setup(finished_store):
    """A 404 is a setup error, not a retry loop: DDL is out of band, so
    the error must say to run bq/setup-bq.sh."""
    db_path, episode_id = finished_store

    class NotFound(Exception):
        pass

    class NoTables(FakeBq):
        def insert_rows_json(self, table_id, rows, row_ids=None):
            raise NotFound(f"404 {table_id}")

    with pytest.raises(RuntimeError, match="setup-bq.sh"):
        bq_export.export_episode(db_path, phase="ladder_complete",
                                 episode_id=episode_id, client=NoTables())


def test_row_id_is_content_sensitive_but_retry_stable():
    row_a = {"episode_id": "ep_1", "status": "awaiting_outcome"}
    id_1 = bq_export._row_id("ladder_complete", "ep_1", row_a)
    assert id_1 == bq_export._row_id("ladder_complete", "ep_1", dict(row_a))
    changed = bq_export._row_id("ladder_complete", "ep_1",
                                dict(row_a, status="closed"))
    assert changed != id_1
