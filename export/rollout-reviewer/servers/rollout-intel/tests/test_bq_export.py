"""bq_export: the BigQuery episode exporter (compat/gcp-harness).

Runs entirely without google-cloud-bigquery: collection and row
preparation are exercised against a real store built through Intel
(begin_review -> record x3 -> outcome label), and the upload path is
driven with a fake client capturing insert_rows_json calls
(ensure_schema=False keeps the lazy BQ import untouched).
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
    with pytest.raises(LookupError, match="not finished"):
        bq_export.collect_episode_rows(db_path, out["episode_id"])
    forced = bq_export.collect_episode_rows(db_path, out["episode_id"],
                                            force=True)
    assert len(forced["episodes"]) == 1
    with pytest.raises(LookupError, match="unknown episode"):
        bq_export.collect_episode_rows(db_path, "ep_nope")


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
        client=fake, ensure_schema=False, export_session="sess-2",
        scrub_text=lambda s: s.replace("SENSITIVE", "[RED]"),
        scrub_json=lambda obj: obj)
    assert summary["episodes"] == 1 and summary["checkpoints"] == 2
    by_table = {t.split(".")[-1]: (rows, ids) for t, rows, ids in fake.calls}
    assert set(by_table) == {f"rollout_{t}" for t in summary}
    checkpoint_rows, checkpoint_ids = by_table["rollout_checkpoints"]
    assert all("[RED]" in r["report_md"] and "SENSITIVE" not in r["report_md"]
               for r in checkpoint_rows)
    assert all(r["export_phase"] == "ladder_complete"
               and r["export_session"] == "sess-2"
               and r["exported_at"] for r in checkpoint_rows)
    assert checkpoint_ids == [f"ladder_complete:{r['checkpoint_id']}"
                              for r in checkpoint_rows]
    outcome_rows, _ = by_table["rollout_outcomes"]
    assert "[RED]" in outcome_rows[0]["notes"]
    # JSON columns stay JSON-formatted strings.
    episode_rows, _ = by_table["rollout_episodes"]
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
                                 client=Rejecting(), ensure_schema=False)


def test_timestamp_sanitizer_and_finished_finder(finished_store):
    db_path, episode_id = finished_store
    assert bq_export._ts("2026-08-09T03:00:00Z") == "2026-08-09T03:00:00Z"
    assert bq_export._ts("+30m") is None  # next_check_at is NOT a timestamp
    assert bq_export._ts(None) is None
    assert "next_check_at" not in bq_export._TIMESTAMP_COLS
    assert bq_export.find_finished_episodes(db_path) == [episode_id]
