"""Event-driven lifecycle: audit-log triggers, deferred checks, and the
session-store plumbing.

Trigger parsing is exercised against sanitized REAL audit-log entries
from the target harness (GKE workload update, App Lifecycle Manager
rollout, a generic container-API entry, an AI Platform entry whose
resourceName names no resource). Lifecycle tests drive Intel.begin_review
end to end: episode birth, at-least-once dedupe, deferred continuation,
ladder-end refusal, closed-episode refusal, and the delay_seconds the
defer tool arms with. Db.flush / Intel.rebind cover the GCS session-DB
cycle. REST tests bind build_rest() to an ephemeral loopback port.
"""

import importlib.util
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import httpx
import pytest
import yaml

import rollout_intel.service as service_module
from rollout_intel import triggers
from rollout_intel.db import Db
from rollout_intel.models import Episode
from rollout_intel.service import Intel, build_rest, episode_id_for_ref

# --- sanitized real events ---------------------------------------------------

GKE_EVENT = {
    "insertId": "7e67c7e4-4680-4597-b0fe-ba16f87baeee",
    "logName": "projects/dev52-test-apps-gke-dev-apps/logs/"
               "cloudaudit.googleapis.com%2Factivity",
    "protoPayload": {
        "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
        "methodName": "io.k8s.apps.v1.deployments.update",
        "resourceName": "apps/v1/namespaces/kube-system/deployments/"
                        "mdp-controller",
        "serviceName": "k8s.io",
        "requestMetadata": {"callerSuppliedUserAgent": "Go-http-client/1.1"},
        "request": {
            "@type": "apps.k8s.io/v1.Deployment",
            # Client-controlled free text: identity must NOT come from here.
            "metadata": {"name": "mdp-controller",
                         "labels": {"app": "attacker-chosen-name"}},
            "spec": {
                "strategy": {"type": "RollingUpdate"},
                "template": {"spec": {"containers": [{
                    "name": "mdp-controller",
                    "image": "gcr.io/gke-release/asm/mdp:1.23.6-asm.36"}]}},
            },
        },
    },
    "resource": {"labels": {"cluster_name": "dev52-generic-cluster-01",
                            "location": "us-central1",
                            "project_id": "dev52-test-apps-gke-dev-apps"},
                 "type": "k8s_cluster"},
    "timestamp": "2026-08-08T22:34:04.756054Z",
    "agent_template": "rollout-reviewer",
}

ALM_EVENT = {
    "insertId": "1nf0p8ldu1kr",
    "logName": "projects/cloud-assist-fde-2/logs/"
               "cloudaudit.googleapis.com%2Factivity",
    "protoPayload": {
        "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
        "methodName": "google.cloud.saasplatform.saasservicemgmt.v1beta1."
                      "SaasRollouts.CreateRollout",
        "resourceName": "projects/cloud-assist-fde-2/locations/us-central1",
        "serviceName": "saasservicemgmt.googleapis.com",
        "request": {
            "rollout": {
                "release": "projects/cloud-assist-fde-2/locations/us-central1/"
                           "releases/rel-gke-infra-v1-1461-0",
                "rolloutKind": "projects/cloud-assist-fde-2/locations/"
                               "us-central1/rolloutKinds/gke-infra-rollout-kind",
            },
            "rolloutId": "rollout-rel-gke-infra-v1-1461-0-1786226661",
        },
    },
    "resource": {"labels": {"project_id": "cloud-assist-fde-2"},
                 "type": "audited_resource"},
    "timestamp": "2026-08-08T22:04:21.936775707Z",
    "agent_template": "rollout-reviewer",
}

GENERIC_EVENT = {
    "id": "replay-rollout-reviewer-726142",  # ce-id; real replay events carry both
    "insertId": "replay-rollout-reviewer-726142",
    "protoPayload": {
        "methodName": "v1.compute.instances.insert",
        "serviceName": "container.googleapis.com",
        "resourceName": "projects/astral-root-454800-c0/zones/us-central1-a/"
                        "clusters/gke-cluster-1",
    },
    "timestamp": "2026-07-22T00:44:00Z",
    "agent_template": "rollout-reviewer",
}

AIP_EVENT = {
    "insertId": "-dl87ogcqjk",
    "operation": {"id": "projects/8532398837/locations/us-central1/"
                        "reasoningEngines/2227239472699801600/operations/"
                        "2401552614488539136",
                  "producer": "aiplatform.googleapis.com"},
    "protoPayload": {
        "methodName": "google.cloud.aiplatform.v1beta1."
                      "ReasoningEngineService.CreateReasoningEngine",
        # A bare container path: names no resource by itself.
        "resourceName": "projects/cloud-assist-fde-1/locations/us-central1",
        "serviceName": "aiplatform.googleapis.com",
    },
    "resource": {"labels": {"project_id": "cloud-assist-fde-1"},
                 "type": "audited_resource"},
    "agent_template": "rollout-reviewer",
}

DEFERRED = {"type": "deferred_check", "target_time": "2026-08-08T22:40:42Z",
            "unique_id": GKE_EVENT["insertId"],
            "agent_template": "rollout-reviewer", "tool_call_count": 340}


UNIT_OP_EVENT = {
    "insertId": "1kxeit0d3alz",
    "protoPayload": {
        "methodName": "google.cloud.saasplatform.saasservicemgmt.v1beta1."
                      "SaasDeployments.CreateUnitOperation",
        "resourceName": "projects/cloud-assist-fde-2/locations/us-central1",
        "serviceName": "saasservicemgmt.googleapis.com",
        "request": {"unitOperation": {
            "provision": {"release": "projects/cloud-assist-fde-2/locations/"
                                     "us-central1/releases/rel-gke-app-v1-1425-0"},
            "unit": "projects/cloud-assist-fde-2/locations/us-central1/"
                    "units/gke-app-unit"},
            "unitOperationId": "prov-gke-app-unit-1786092521"},
    },
    "resource": {"labels": {"project_id": "cloud-assist-fde-2"}},
    "timestamp": "2026-08-07T08:48:42.376148472Z",
}

# Bare replayed entries: no insertId, no timestamp, no logName.
CLUSTER_UPDATE_EVENT = {
    "protoPayload": {"serviceName": "container.googleapis.com",
                     "methodName": "google.container.v1.ClusterManager."
                                   "UpdateCluster",
                     "resourceName": "projects/astral-root-454800-c0/"
                                     "locations/us-central1/clusters/"
                                     "test-cluster"},
    "agent_template": "default",
}

NODE_INSERT_EVENT = {
    "protoPayload": {"serviceName": "container.googleapis.com",
                     "methodName": "v1.compute.instances.insert",
                     "resourceName": "projects/astral-root-454800-c0/zones/"
                                     "us-central1-a/instances/node-5"},
}

K8S_CREATE_EVENT = {
    "insertId": "04d277bc-898f-4f43-a153-93a8accd4d9a",
    "protoPayload": {
        "methodName": "io.k8s.apps.v1.deployments.create",
        "serviceName": "k8s.io",
        "resourceName": "apps/v1/namespaces/gmk-426b/deployments/"
                        "gmk-per-cluster-prober",
        "request": {"spec": {
            "strategy": {"type": "Recreate"},
            "template": {"spec": {"containers": [{
                "name": "gmk-per-cluster-prober",
                "image": "us-central1-docker.pkg.dev/x/per-cluster-prober"
                         "@sha256:50630ea9"}]}}}},
    },
    "resource": {"labels": {"cluster_name": "gke-4a401a86f47caea6",
                            "location": "us-central1",
                            "project_id": "e09f1c009eec06fa9p-tp"}},
    "timestamp": "2026-08-08T12:16:27.99783Z",
}

K8S_PATCH_EVENT = {
    "insertId": "4e45e33f-f2bb-4419-b7a2-7f5ef99b8cfb",
    "protoPayload": {
        "methodName": "io.k8s.apps.v1.deployments.patch",
        "serviceName": "k8s.io",
        "resourceName": "apps/v1/namespaces/gmk-4a6f/deployments/"
                        "gmk-per-cluster-prober",
        # A patch delta that DOES touch the image.
        "request": {"@type": "k8s.io/Patch", "spec": {"template": {"spec": {
            "containers": [{"image": "us-central1-docker.pkg.dev/x/"
                                     "per-cluster-prober@sha256:52c7c505",
                            "name": "gmk-per-cluster-prober"}]}}}},
        "response": {"spec": {
            "strategy": {"type": "Recreate"},
            "template": {"spec": {"containers": [{
                "name": "gmk-per-cluster-prober",
                "image": "us-central1-docker.pkg.dev/x/per-cluster-prober"
                         "@sha256:52c7c505"}]}}}},
    },
    "resource": {"labels": {"cluster_name": "gke-4a401a86f47caea6",
                            "location": "us-central1",
                            "project_id": "e09f1c009eec06fa9p-tp"}},
    "timestamp": "2026-08-09T02:50:21.331082Z",
}


# --- trigger parsing ---------------------------------------------------------


def test_gke_workload_event_parses_from_authoritative_fields():
    ev = triggers.parse_trigger(GKE_EVENT)
    assert ev["service"] == "mdp-controller"  # resourceName, not labels
    assert "attacker-chosen-name" not in str(ev["service"])
    assert ev["region"] == "us-central1"
    assert ev["project"] == "dev52-test-apps-gke-dev-apps"
    assert ev["to_revision"] == "gcr.io/gke-release/asm/mdp:1.23.6-asm.36"
    assert ev["change_classes"] == ["application_binary"]
    assert ev["strategy"] == "rolling_update"
    assert ev["external_ref"] == GKE_EVENT["insertId"]
    assert ev["trigger"]["family"] == "gke-workload"
    assert ev["trigger"]["cluster"] == "dev52-generic-cluster-01"


def test_alm_rollout_event_parses_kind_and_release():
    ev = triggers.parse_trigger(ALM_EVENT)
    assert ev["service"] == "gke-infra"
    assert ev["to_revision"] == "rel-gke-infra-v1-1461-0"
    assert ev["region"] == "us-central1"
    assert ev["project"] == "cloud-assist-fde-2"
    assert ev["change_classes"] == ["release"]
    assert ev["trigger"]["family"] == "saas-rollout"


def test_generic_event_takes_final_resource_and_normalizes_zone():
    ev = triggers.parse_trigger(GENERIC_EVENT)
    assert ev["service"] == "gke-cluster-1"
    assert ev["region"] == "us-central1"  # us-central1-a normalized
    assert ev["trigger"]["family"] == "generic"
    # A top-level CloudEvents id is captured as provenance; events
    # without one simply omit the key.
    assert ev["trigger"]["event_id"] == GENERIC_EVENT["id"]
    assert "event_id" not in triggers.parse_trigger(GKE_EVENT)["trigger"]


def test_bare_container_resource_falls_back_to_operation_target():
    ev = triggers.parse_trigger(AIP_EVENT)
    assert ev["service"] == "reasoningEngines-2227239472699801600"
    assert ev["region"] == "us-central1"


def test_unit_operation_parses_unit_and_release_as_request_derived():
    ev = triggers.parse_trigger(UNIT_OP_EVENT)
    assert ev["service"] == "gke-app-unit"
    assert ev["to_revision"] == "rel-gke-app-v1-1425-0"
    assert ev["strategy"] == "provision"
    assert ev["change_classes"] == ["release"]
    assert ev["region"] == "us-central1"
    assert ev["identity_basis"] == "request"  # unit is a request field
    assert ev["trigger"]["family"] == "saas-unit-operation"


def test_bare_event_without_insert_id_gets_deterministic_synth_ref():
    ev = triggers.parse_trigger(CLUSTER_UPDATE_EVENT)
    assert ev["service"] == "test-cluster"
    assert ev["region"] == "us-central1"
    assert ev["external_ref"].startswith("synth-")
    assert ev["trigger"]["ref_basis"] == "synthesized"
    # Deterministic: the same event always yields the same ref (dedupe),
    # a different resource yields a different one.
    assert triggers.parse_trigger(CLUSTER_UPDATE_EVENT)["external_ref"] == \
        ev["external_ref"]
    assert triggers.parse_trigger(NODE_INSERT_EVENT)["external_ref"] != \
        ev["external_ref"]


def test_node_insert_parses_generically():
    ev = triggers.parse_trigger(NODE_INSERT_EVENT)
    assert ev["service"] == "node-5"
    assert ev["region"] == "us-central1"
    assert ev["trigger"]["family"] == "generic"


def test_k8s_create_takes_strategy_and_image_from_request():
    ev = triggers.parse_trigger(K8S_CREATE_EVENT)
    assert ev["service"] == "gmk-per-cluster-prober"
    assert ev["strategy"] == "recreate"
    assert ev["to_revision"].endswith("@sha256:50630ea9")
    assert ev["change_classes"] == ["application_binary"]


def test_k8s_patch_image_delta_is_binary_change_config_delta_is_not():
    ev = triggers.parse_trigger(K8S_PATCH_EVENT)
    assert ev["to_revision"].endswith("@sha256:52c7c505")
    assert ev["change_classes"] == ["application_binary"]
    assert ev["strategy"] == "recreate"  # from the response echo
    # A patch whose delta does NOT touch the image: the revision comes
    # from the response echo (what is running), but the change class is
    # workload_config — the binary did not change.
    config_only = {**K8S_PATCH_EVENT,
                   "protoPayload": {**K8S_PATCH_EVENT["protoPayload"],
                                    "request": {"@type": "k8s.io/Patch",
                                                "metadata": {"annotations": {
                                                    "x": "y"}}}}}
    ev2 = triggers.parse_trigger(config_only)
    assert ev2["to_revision"].endswith("@sha256:52c7c505")
    assert ev2["change_classes"] == ["workload_config"]


def test_synth_ref_round_trips_through_the_defer_lifecycle(
        make_intel, time_travel):
    """An insertId-less event still gets full correlation: the recorder
    returns the synthesized unique_id, the agent arms it, and the
    deferred check resolves the episode from it."""
    intel = make_intel()
    out = intel.begin_review(CLUSTER_UPDATE_EVENT, "sess-1")
    assert out["status"] == "review_due"
    assert out["unique_id"].startswith("synth-")
    r = record(intel, out["episode_id"], "G+0")
    assert r["next_check"]["unique_id"] == out["unique_id"]
    time_travel(11)
    resumed = intel.begin_review(
        {"type": "deferred_check", "unique_id": out["unique_id"]}, "sess-2")
    assert resumed["status"] == "review_due"
    assert resumed["stage"] == "G+10"
    assert resumed["episode_id"] == out["episode_id"]


def test_bare_events_for_distinct_targets_get_distinct_synth_refs():
    """Two insertId-less events under the same bare parent resourceName
    (different operation targets) must not share a ref — a shared ref
    would hard-fail the second forever via the collision guard."""
    def aip(engine_id):
        return {"protoPayload": {
                    "methodName": "google.cloud.aiplatform.v1."
                                  "ReasoningEngineService.CreateReasoningEngine",
                    "resourceName": "projects/p/locations/us-central1",
                    "serviceName": "aiplatform.googleapis.com"},
                "operation": {"id": f"projects/8/locations/us-central1/"
                                    f"reasoningEngines/{engine_id}/"
                                    f"operations/1"}}
    a, b = triggers.parse_trigger(aip("1111")), triggers.parse_trigger(aip("2222"))
    assert a["service"] != b["service"]
    assert a["external_ref"] != b["external_ref"]
    assert a["external_ref"] == triggers.parse_trigger(aip("1111"))["external_ref"]


def test_multi_container_patch_attributes_binary_change_to_app_container():
    delta = {"insertId": "mc-1", "protoPayload": {
        "methodName": "io.k8s.apps.v1.deployments.patch",
        "serviceName": "k8s.io",
        "resourceName": "apps/v1/namespaces/ns/deployments/myapp",
        # Sidecar listed first with no image; the app ships a new binary.
        "request": {"@type": "k8s.io/Patch", "spec": {"template": {"spec": {
            "containers": [{"name": "istio-proxy"},
                           {"name": "myapp",
                            "image": "gcr.io/x/myapp@sha256:NEW"}]}}}},
        "response": {"spec": {"template": {"spec": {"containers": [
            {"name": "istio-proxy", "image": "gcr.io/x/proxy:1.2"},
            {"name": "myapp", "image": "gcr.io/x/myapp@sha256:NEW"}]}}}},
    }}
    ev = triggers.parse_trigger(delta)
    assert ev["change_classes"] == ["application_binary"]
    assert ev["to_revision"] == "gcr.io/x/myapp@sha256:NEW"  # not the sidecar


def test_full_spec_with_sidecar_first_picks_service_named_image():
    full = {"insertId": "mc-2", "protoPayload": {
        "methodName": "io.k8s.apps.v1.deployments.update",
        "serviceName": "k8s.io",
        "resourceName": "apps/v1/namespaces/ns/deployments/myapp",
        "request": {"spec": {"template": {"spec": {"containers": [
            {"name": "istio-proxy", "image": "gcr.io/x/proxy:1.2"},
            {"name": "myapp", "image": "gcr.io/x/myapp@sha256:APP"}]}}}},
    }}
    assert triggers.parse_trigger(full)["to_revision"] == \
        "gcr.io/x/myapp@sha256:APP"


def test_unreadable_patch_encoding_never_claims_config_only():
    base = {"insertId": "op-1", "protoPayload": {
        "methodName": "io.k8s.apps.v1.deployments.patch",
        "serviceName": "k8s.io",
        "resourceName": "apps/v1/namespaces/ns/deployments/myapp",
        "request": {"@type": "k8s.io/Patch",
                    "ops": [{"op": "replace",
                             "path": "/spec/template/spec/containers/0/image",
                             "value": "gcr.io/x/myapp@sha256:Z"}]}}}
    assert triggers.parse_trigger(base)["change_classes"] == \
        ["application_binary"]
    opaque = {**base, "protoPayload": {**base["protoPayload"],
                                       "request": {"@type": "k8s.io/Patch"}}}
    assert triggers.parse_trigger(opaque)["change_classes"] == \
        ["workload_change"]


def test_non_dict_unit_operation_is_a_loud_valueerror():
    bad = {**UNIT_OP_EVENT,
           "protoPayload": {**UNIT_OP_EVENT["protoPayload"],
                            "request": {"unitOperation": "prov-x"}}}
    with pytest.raises(ValueError, match="no service derivable"):
        triggers.parse_trigger(bad)


def test_catalog_rejects_reserved_inferred_tenants(tmp_path):
    from rollout_intel import identity
    for tenant in ("inferred", "inferred-request"):
        bad = tmp_path / f"bad-{tenant}.yaml"
        bad.write_text(yaml.safe_dump({"services": [
            {"tenant": tenant, "name": "checkout", "environment": "prod",
             "region": "us-east1"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="reserved"):
            identity.load_catalog(Db(str(tmp_path / f"{tenant}.db")), str(bad))


def test_unrecognizable_and_deferred_triggers_fail_loudly():
    with pytest.raises(ValueError, match="methodName"):
        triggers.parse_trigger({"textPayload": "something happened"})
    with pytest.raises(ValueError, match="no service derivable"):
        triggers.parse_trigger({"protoPayload": {"methodName": "x.y.z",
                                                 "resourceName": ""}})
    with pytest.raises(ValueError, match="continuation"):
        triggers.parse_trigger(DEFERRED)
    assert triggers.is_deferred_check(DEFERRED)
    assert triggers.deferred_ref(DEFERRED) == GKE_EVENT["insertId"]
    with pytest.raises(ValueError, match="unique_id"):
        triggers.deferred_ref({"type": "deferred_check"})


# --- lifecycle: begin_review -------------------------------------------------

CATALOG = {"services": [
    {"tenant": "autocloud", "name": "checkout", "environment": "prod",
     "region": "us-east1", "runtime": "cloud-run",
     "architecture_version": "v1", "owner": "team-payments"},
]}

TRIGGER_POLICY = {
    "name": "trigger-pack", "version": 1,
    "rules": [{"id": "wl", "type": "workload_serving", "stages": ["G+0"]}],
    "checkpoints": {
        "ladder": [{"stage": "G+0", "offset_minutes": 0},
                   {"stage": "G+10", "offset_minutes": 10},
                   {"stage": "G+30", "offset_minutes": 30}],
        "bounds": {"min_interval_minutes": 2, "max_interval_minutes": 60},
    },
}


@pytest.fixture
def make_intel(tmp_path, monkeypatch):
    monkeypatch.delenv("ENSEMBLE_TOKEN", raising=False)

    def _make(policy_doc=TRIGGER_POLICY, db_name="intel.db"):
        policy = tmp_path / "policy.yaml"
        policy.write_text(yaml.safe_dump(policy_doc), encoding="utf-8")
        catalog = tmp_path / "services.yaml"
        catalog.write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
        return Intel(str(tmp_path / db_name), str(policy), str(catalog))

    return _make


@pytest.fixture
def time_travel(monkeypatch):
    """Shift the SERVICE module's clock forward by N minutes. The db
    module's stamps (completed_at etc.) stay real, so the not-before
    gate sees genuinely elapsed time — the same asymmetry a real
    deferred check experiences."""

    def _shift(minutes):
        shifted = time.time() + minutes * 60
        monkeypatch.setattr(
            service_module, "now_iso",
            lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(shifted)))

    return _shift


def record(intel, episode, stage, **kwargs):
    return intel.record(episode, stage, [], "insufficient-evidence",
                        "reasoning", "# report", [], [], **kwargs)


def test_trigger_births_episode_and_opens_first_stage(make_intel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    assert out["status"] == "review_due"
    assert out["stage"] == "G+0"
    assert out["episode_id"] == episode_id_for_ref(GKE_EVENT["insertId"])
    assert out["service"] == "mdp-controller"
    assert out["identity_status"] == "candidate"  # not in the catalog
    assert out["deduplicated"] is False
    assert out["prior_checkpoints"] == []


def test_redelivered_trigger_dedupes_onto_same_episode(make_intel):
    intel = make_intel()
    first = intel.begin_review(GKE_EVENT, "sess-1")
    again = intel.begin_review(GKE_EVENT, "sess-2")
    assert again["episode_id"] == first["episode_id"]
    assert again["deduplicated"] is True
    assert again["status"] == "review_due"
    assert again["stage"] == "G+0"  # same open checkpoint, re-armed
    assert again["checkpoint_id"] == first["checkpoint_id"]


def test_deferred_check_resumes_next_stage_with_governed_delay(
        make_intel, time_travel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    assert out["unique_id"] == GKE_EVENT["insertId"]
    r = record(intel, out["episode_id"], "G+0")
    assert r["next_check"]["minutes"] == 10
    assert r["next_check"]["delay_seconds"] == 600  # defer_verification args
    assert r["next_check"]["unique_id"] == GKE_EVENT["insertId"]
    time_travel(11)
    resumed = intel.begin_review(DEFERRED, "sess-2")
    assert resumed["status"] == "review_due"
    assert resumed["stage"] == "G+10"
    assert resumed["episode_id"] == out["episode_id"]
    assert resumed["prior_checkpoints"] == [
        {"stage": "G+0", "stage_verdict": "insufficient-evidence",
         "policy_status": "insufficient_evidence"}]


def test_early_or_duplicate_timer_bounces_off_not_before_gate(
        make_intel, time_travel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    record(intel, out["episode_id"], "G+0")  # decides +10m
    early = intel.begin_review(DEFERRED, "sess-dup")  # fires immediately
    assert early["status"] == "not_due"
    assert early["stage"] is None
    assert 0 < early["seconds_remaining"] <= 600
    # No G+10 checkpoint was opened by the early fire.
    assert intel.open_checkpoint_for(out["episode_id"], "G+10") is None
    time_travel(11)
    assert intel.begin_review(DEFERRED, "sess-2")["stage"] == "G+10"


def test_tightening_proposal_flows_into_delay_seconds(make_intel, time_travel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    r = record(intel, out["episode_id"], "G+0",
               next_check_proposal_minutes=4,
               next_check_reason="sample floor reached in ~4m")
    assert r["next_check"]["delay_seconds"] == 240
    time_travel(5)
    intel.begin_review(DEFERRED, "sess-2")  # opens G+10
    r2 = record(intel, out["episode_id"], "G+10",
                next_check_proposal_minutes=1)  # under min_interval 2
    assert r2["next_check"]["minutes"] == 2
    assert r2["next_check"]["delay_seconds"] == 120


def test_sub_minute_scheduling_via_fractional_minutes(make_intel, time_travel):
    """Minutes are the POLICY unit; seconds are the EXECUTION unit
    (delay_seconds). Both are floats end to end, so a policy that wants
    sub-minute cadence just authors fractional bounds - nothing in the
    chain is quantized to whole minutes."""
    fast = {**TRIGGER_POLICY,
            "checkpoints": {**TRIGGER_POLICY["checkpoints"],
                            "bounds": {"min_interval_minutes": 0.25,
                                       "max_interval_minutes": 60}}}
    intel = make_intel(fast)
    out = intel.begin_review(GKE_EVENT, "sess-1")
    r = record(intel, out["episode_id"], "G+0",
               next_check_proposal_minutes=0.5,
               next_check_reason="sample floor reached in ~30s")
    assert r["next_check"]["minutes"] == 0.5
    assert r["next_check"]["delay_seconds"] == 30  # what the timer arms
    assert r["next_check_at"] == "+0.5m"  # stored decision keeps fractions
    time_travel(1)
    assert intel.begin_review(DEFERRED, "sess-2")["stage"] == "G+10"


def test_deferred_check_after_ladder_end_arms_nothing(make_intel, time_travel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    for shift, stage in ((0, "G+0"), (11, "G+10"), (32, "G+30")):
        time_travel(shift)
        intel.begin_review(DEFERRED, "sess-x")  # idempotent open
        r = record(intel, out["episode_id"], stage)
    assert r["next_check_at"] is None
    late = intel.begin_review(DEFERRED, "sess-late")
    assert late["status"] == "ladder_complete"
    assert late["stage"] is None
    assert "arm no further checks" in late["note"]


def test_deferred_check_on_labeled_episode_reports_closed(make_intel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    with intel.db.session() as s:
        episode = s.get(Episode, out["episode_id"])
        episode.final_label = "healthy"
        episode.status = "closed"
    closed = intel.begin_review(DEFERRED, "sess-2")
    assert closed["status"] == "closed"
    assert closed["stage"] is None


def test_deferred_check_with_unknown_ref_errors(make_intel):
    intel = make_intel()
    out = intel.begin_review({**DEFERRED, "unique_id": "never-seen"}, "s")
    assert "never reviewed" in out["error"]


def test_failed_operation_births_no_episode():
    denied = {**ALM_EVENT,
              "protoPayload": {**ALM_EVENT["protoPayload"],
                               "status": {"code": 7,
                                          "message": "PERMISSION_DENIED"}}}
    with pytest.raises(ValueError, match="FAILED operation"):
        triggers.parse_trigger(denied)


def test_request_derived_identity_never_confirms_against_catalog(make_intel):
    """A caller-chosen rolloutKind naming a real catalog service must not
    bind its episode to the CONFIRMED catalog identity."""
    intel = make_intel()
    spoof = {**ALM_EVENT,
             "protoPayload": {
                 **ALM_EVENT["protoPayload"],
                 "resourceName": "projects/x/locations/us-east1",
                 "request": {"rollout": {
                     "release": "projects/x/locations/us-east1/releases/r1",
                     "rolloutKind": "projects/x/locations/us-east1/"
                                    "rolloutKinds/checkout-rollout-kind"}}},
             "resource": {"labels": {"project_id": "x"}}}
    ev = triggers.parse_trigger(spoof)
    assert ev["service"] == "checkout" and ev["region"] == "us-east1"
    assert ev["identity_basis"] == "request"
    out = intel.begin_review(spoof, "sess-1")
    # The catalog's confirmed checkout (us-east1) is NOT bound, and the
    # request-derived candidate lives in its own partitioned namespace —
    # it can never inherit a platform-derived candidate's history.
    assert out["identity_status"] == "candidate"
    assert out["service_uid"].startswith("svc://inferred-request/")


def test_insert_id_collision_errors_instead_of_silently_merging(make_intel):
    intel = make_intel()
    intel.begin_review(GKE_EVENT, "sess-1")
    collided = {**GENERIC_EVENT, "insertId": GKE_EVENT["insertId"]}
    with pytest.raises(ValueError, match="correlation collision"):
        intel.begin_review(collided, "sess-2")


def test_open_checkpoint_refuses_closed_episode_atomically(make_intel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    with intel.db.session() as s:
        episode = s.get(Episode, out["episode_id"])
        episode.final_label = "healthy"
    with pytest.raises(ValueError, match="closed"):
        intel.db.open_checkpoint(out["episode_id"], "G+10", "s", "t",
                                 refuse_closed=True)


def test_session_store_rejects_traversal_session_ids():
    spec = importlib.util.spec_from_file_location(
        "session_db_under_test",
        Path(__file__).resolve().parents[3] / "compat" / "gcp-harness"
        / "session_db.py")
    session_db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(session_db)
    for bad in ("..", ".", "", "a/b", "../etc", ".hidden", "a" * 200):
        with pytest.raises((ValueError, KeyError)):
            session_db.SessionStore(bad, bucket="b")
    ok = session_db.SessionStore("run-2026.08.09_x", bucket="b")
    assert ok.db_path == "/tmp/sessions/run-2026.08.09_x/intel.db"
    assert ok.blob_name == "sessions/run-2026.08.09_x/intel.db"


# --- session-store plumbing: flush and rebind --------------------------------


def test_db_flush_merges_wal_into_main_file(tmp_path):
    db = Db(str(tmp_path / "x.db"))
    db.upsert_service({"service_uid": "svc://t/a/prod/r", "name": "a",
                       "environment": "prod", "region": "r"})
    wal = tmp_path / "x.db-wal"
    assert wal.exists() and wal.stat().st_size > 0  # WAL mode is on
    out = db.flush()
    assert out["flushed"] is True
    # TRUNCATE empties the wal; closing the last connection may then
    # remove the file entirely — both states mean "nothing left behind".
    assert not wal.exists() or wal.stat().st_size == 0
    # The main file ALONE is now the complete store (what gets uploaded).
    shutil.copyfile(tmp_path / "x.db", tmp_path / "uploaded.db")
    conn = sqlite3.connect(tmp_path / "uploaded.db")
    try:
        n = conn.execute("SELECT count(*) FROM services").fetchone()[0]
    finally:
        conn.close()
    assert n == 1
    # The engine survives a flush: connections re-create lazily.
    assert db.get_service("svc://t/a/prod/r") is not None


def test_exclusive_is_mutually_exclusive_between_writers(make_intel):
    """flush/rebind/reset must never interleave: a second writer waits
    for the first, and the first's exit must not admit readers while the
    second is still inside its critical section."""
    intel = make_intel()
    order = []
    a_inside = threading.Event()
    a_release = threading.Event()

    def writer_a():
        with intel.exclusive():
            order.append("a-in")
            a_inside.set()
            a_release.wait(5)
            order.append("a-out")

    def writer_b():
        a_inside.wait(5)
        with intel.exclusive():
            order.append("b-in")

    ta = threading.Thread(target=writer_a)
    tb = threading.Thread(target=writer_b)
    ta.start(); tb.start()
    assert a_inside.wait(5)
    time.sleep(0.3)  # give writer B every chance to (wrongly) slip in
    assert "b-in" not in order
    a_release.set()
    ta.join(5); tb.join(5)
    assert order == ["a-in", "a-out", "b-in"]


def test_rebind_failure_keeps_previous_binding_intact(make_intel):
    intel = make_intel()
    out = intel.begin_review(GKE_EVENT, "sess-1")
    with pytest.raises(Exception):
        intel.rebind("/nonexistent-dir-for-sure/deeper/x.db")
    # The old binding still serves, coherently: db, dossiers, episodes.
    assert intel.dossiers.db is intel.db
    with intel.db.session() as s:
        assert s.get(Episode, out["episode_id"]) is not None
    # And the gate is released — a follow-up writer does not deadlock.
    assert intel.flush()["flushed"] is True


def test_intel_rebind_moves_every_component_to_the_new_store(make_intel):
    intel = make_intel()
    old = intel.begin_review(GKE_EVENT, "sess-1")
    intel.rebind(str_path := intel.db_path + ".next")
    assert intel.db_path == str_path
    # The dossier store follows — the naive `intel.db = Db(path)` would not.
    assert intel.dossiers.db is intel.db
    # Catalog reloaded on the new store; old episode is not there.
    assert intel.resolve_service_uid("checkout") is not None
    with intel.db.session() as s:
        assert s.get(Episode, old["episode_id"]) is None


# --- REST faces --------------------------------------------------------------


def test_rest_triggers_by_ref_and_flush(make_intel):
    intel = make_intel()
    server = build_rest(intel, 0)  # ephemeral loopback port
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        r = httpx.post(f"{base}/intel/triggers?session_id=s1",
                       json=GKE_EVENT, timeout=10)
        assert r.status_code == 200 and r.json()["status"] == "review_due"
        episode_id = r.json()["episode_id"]

        by_ref = httpx.get(f"{base}/intel/episodes/by-ref",
                           params={"ref": GKE_EVENT["insertId"]}, timeout=10)
        assert by_ref.status_code == 200
        assert by_ref.json()["episode_id"] == episode_id
        assert httpx.get(f"{base}/intel/episodes/by-ref",
                         params={"ref": "nope"}, timeout=10).status_code == 404
        # The by-ref branch must not shadow /intel/episodes/{id}.
        assert httpx.get(f"{base}/intel/episodes/{episode_id}",
                         timeout=10).status_code == 200

        bad = httpx.post(f"{base}/intel/triggers",
                         json={"textPayload": "hi"}, timeout=10)
        assert bad.status_code == 400

        flushed = httpx.post(f"{base}/intel/flush", json={}, timeout=10)
        assert flushed.status_code == 200 and flushed.json()["flushed"] is True
    finally:
        server.shutdown()
