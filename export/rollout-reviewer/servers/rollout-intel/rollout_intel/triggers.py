"""Trigger intake: platform audit-log events -> deploy events.

Event-driven harnesses do not synthesize a neat deploy_event: episodes
are born from Cloud Audit Log entries (a GKE workload update, an App
Lifecycle Manager rollout, a Cloud Run service change) and continued by
deferred_check notices whose only payload is the correlation id of the
original event. This module is the ONE place that turns a raw event
into the deploy_event shape create_episode expects — deterministic
server-side code, so identity extraction is never the LLM's job.

Trust posture: parsing reads only platform-authoritative fields
(protoPayload.methodName / resourceName / serviceName, resource.labels,
operation.id, insertId, timestamp). Client-influenced free text —
k8s labels/annotations, callerSuppliedUserAgent, request bodies beyond
the workload spec — never chooses identity: whoever controls a request
body must not choose which service an episode binds to. One documented
exception: the two SaaS families' names come from the request body
(rolloutKind for rollouts, the target unit for unit operations — their
resourceName names only the parent location) — such events are marked
identity_basis="request" and identity.resolve refuses to CONFIRM them
against the catalog; they always land as candidates.
Failed/denied operations (protoPayload.status.code != 0) never birth an
episode. Identity derived here still lands as an inferred CANDIDATE
unless the catalog confirms it (identity.resolve); parsing is
extraction, not authority.
"""

from __future__ import annotations

import hashlib
import json
import re

# Path segments that CONTAIN resources rather than being resources:
# their following segment is a container id, never a service name.
_CONTAINERS = ("projects", "locations", "zones", "regions", "namespaces")


def is_deferred_check(event: dict) -> bool:
    return isinstance(event, dict) and event.get("type") == "deferred_check"


def deferred_ref(event: dict) -> str:
    """The correlation id a deferred_check carries — the insertId of the
    trigger event whose episode this session continues."""
    ref = str(event.get("unique_id", "") or "")
    if not ref:
        raise ValueError("deferred_check carries no unique_id — nothing to "
                         "correlate the episode by")
    return ref


def external_ref(event: dict) -> str:
    """The correlation id of a trigger event (Cloud Logging insertId)."""
    return str(event.get("insertId") or event.get("id") or "")


def _region_of(token: str) -> str:
    # A zone ("us-central1-a") normalizes to its region ("us-central1").
    m = re.fullmatch(r"([a-z]+-[a-z]+\d+)-[a-z]", token)
    return m.group(1) if m else token


def _path_value(path: str, container: str) -> str:
    parts = [p for p in path.split("/") if p]
    for i, part in enumerate(parts[:-1]):
        if part == container:
            return parts[i + 1]
    return ""


def _region_from_path(path: str) -> str:
    for container in ("locations", "regions", "zones"):
        value = _path_value(path, container)
        if value:
            return _region_of(value)
    return ""


def _last_resource(path: str) -> str:
    """The final resource id of a path, skipping container values: for
    'projects/p/zones/z/clusters/c' -> 'c'; for 'projects/p/locations/l'
    -> '' (a bare container path names no resource)."""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[-2] not in _CONTAINERS:
        return parts[-1]
    return ""


def _dig(obj, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return obj if obj is not None else default


def parse_trigger(event: dict) -> dict:
    """Audit-log entry -> deploy_event. Raises ValueError (with the reason)
    when no service identity is derivable — a trigger that cannot name a
    resource must fail loudly, never bind to a guessed service."""
    if not isinstance(event, dict):
        raise ValueError("trigger must be a JSON object")
    if is_deferred_check(event):
        raise ValueError("deferred_check is a continuation notice, not a "
                         "deploy event — resolve its unique_id instead")
    proto = event.get("protoPayload") or {}
    method = str(proto.get("methodName", ""))
    if not method:
        raise ValueError("unrecognized trigger: no protoPayload.methodName")
    # A failed/denied operation deployed nothing: an admission rejection,
    # quota error, or PERMISSION_DENIED attempt is still audit-logged and
    # must not birth a review episode (it would also let denied attempts
    # feed the identity path). gRPC code 0 / absent status = success.
    status = proto.get("status") or {}
    if isinstance(status, dict) and status.get("code"):
        raise ValueError(
            f"trigger records a FAILED operation (status.code="
            f"{status['code']}): nothing was deployed, no episode")
    api = str(proto.get("serviceName", ""))
    resource_name = str(proto.get("resourceName", ""))
    labels = _dig(event, "resource", "labels", default={}) or {}
    ref = external_ref(event)

    service = ""
    region = (_region_of(str(labels.get("location", "")))
              or _region_from_path(resource_name))
    project = str(labels.get("project_id", "")) or _path_value(
        resource_name, "projects")
    to_revision = ""
    image = ""
    strategy = "unknown"
    change_classes = ["platform_change"]
    family = "generic"

    if api == "k8s.io" or method.startswith("io.k8s."):
        # GKE workload change (create/update/patch on deployments,
        # statefulsets, daemonsets, ...): the workload name is the
        # service. The image comes from the SUBMITTED spec when the
        # change carries one (create/update, or a patch whose delta
        # touches the image — that is an application_binary change);
        # otherwise from the API server's response echo, which states
        # what is now running (a config-only change: the revision is
        # context, not what changed).
        family = "gke-workload"
        service = _last_resource(resource_name)

        # Revision and change-class scan the WHOLE container list —
        # multi-container pods routinely list sidecars first, and
        # containers[0] would attribute the sidecar's image as the
        # revision (or miss a binary change shipped on a later entry).
        def _image_pairs(*path):
            containers = _dig(proto, *path, "spec", "template", "spec",
                              "containers", default=[])
            if not isinstance(containers, list):
                return []
            return [(str(c.get("name", "") or ""),
                     str(c.get("image", "") or ""))
                    for c in containers if isinstance(c, dict)]

        request_pairs = _image_pairs("request")
        response_pairs = _image_pairs("response")
        echo = {n: img for n, img in response_pairs if img}

        def _pick(pairs):
            # Preference: the container named like the workload, then a
            # request image differing from the response echo (the actual
            # delta when visible), then the first non-empty image.
            for n, img in pairs:
                if img and n == service:
                    return img
            for n, img in pairs:
                if img and echo.get(n) not in (None, "", img):
                    return img
            return next((img for _, img in pairs if img), "")

        request_image = _pick(request_pairs)
        # A config-only change takes its revision (context, not the
        # change) from the API server's response echo.
        image = request_image or _pick(response_pairs)
        to_revision = image
        if request_image:
            change_classes = ["application_binary"]
        elif (method.endswith(".patch")
              and not isinstance(_dig(proto, "request", "spec"), dict)):
            # No structural spec in the patch. A merge-patch whose delta
            # is other dict sections (metadata-only, say) visibly avoids
            # the pod spec: config-only is an honest claim. An encoding
            # we cannot read structurally (RFC-6902 op lists, uncaptured
            # patch bytes) must never claim config-only: an
            # image-targeting op path upgrades to binary, otherwise the
            # class stays neutral.
            request = proto.get("request")
            body = ({k: v for k, v in request.items() if k != "@type"}
                    if isinstance(request, dict) else None)
            if body and all(isinstance(v, dict) for v in body.values()):
                change_classes = ["workload_config"]
            else:
                raw = json.dumps(request or {}, default=str)
                change_classes = (["application_binary"]
                                  if re.search(r"/containers/\d+/image", raw)
                                  else ["workload_change"])
        else:
            change_classes = ["workload_config"]
        k8s_strategy = (_dig(proto, "request", "spec", "strategy", "type",
                             default="")
                        or _dig(proto, "response", "spec", "strategy",
                                "type", default=""))
        if k8s_strategy:
            strategy = re.sub(r"(?<!^)(?=[A-Z])", "_", str(k8s_strategy)).lower()
    elif "SaasRollouts.CreateRollout" in method:
        # App Lifecycle Manager: the rollout kind names what is being
        # rolled out; the release names the target version. Unlike the
        # other families, this name comes from the REQUEST body (the
        # CreateRollout resourceName is only the parent location), so it
        # is caller-chosen: the deploy event is marked identity_basis=
        # "request" and identity.resolve will never CONFIRM such a name
        # against the catalog — it always lands as a candidate.
        family = "saas-rollout"
        kind = _last_resource(str(_dig(proto, "request", "rollout",
                                       "rolloutKind", default="") or ""))
        service = re.sub(r"-rollout-kind$", "", kind)
        to_revision = _last_resource(str(_dig(proto, "request", "rollout",
                                              "release", default="") or ""))
        strategy = "managed_rollout"
        change_classes = ["release"]
    elif "SaasDeployments.CreateUnitOperation" in method:
        # App Lifecycle Manager unit operation: the target UNIT names the
        # deploy target; the operation payload (provision/upgrade/
        # deprovision) names the release. Same caveat as rollouts — both
        # come from the request body, so identity never confirms.
        family = "saas-unit-operation"
        unit_op = _dig(proto, "request", "unitOperation", default={}) or {}
        if not isinstance(unit_op, dict):
            # A malformed (client-shaped) body falls through to the loud
            # no-service ValueError, same as unitOperation missing.
            unit_op = {}
        service = _last_resource(str(unit_op.get("unit", "") or ""))
        op_kind = next((k for k in ("provision", "upgrade", "deprovision")
                        if isinstance(unit_op.get(k), dict)), "")
        if op_kind:
            to_revision = _last_resource(str(_dig(unit_op, op_kind,
                                                  "release", default="")
                                            or ""))
            strategy = op_kind
        else:
            strategy = "unit_operation"
        change_classes = ["release"] if to_revision else ["unit_operation"]
    elif api == "run.googleapis.com":
        family = "cloud-run"
        service = _path_value(resource_name, "services")
        to_revision = str(_dig(proto, "response", "metadata",
                               "latestCreatedRevisionName", default="") or "")
        change_classes = ["application_binary"]
    else:
        # Generic audit entry: the resourceName's final resource, else the
        # operation's target resource (some APIs put only the parent in
        # resourceName).
        service = _last_resource(resource_name)
        if not service:
            op_path = str(_dig(event, "operation", "id", default="") or "")
            op_path = op_path.split("/operations/")[0]
            tail = _last_resource(op_path)
            if tail:
                parts = [p for p in op_path.split("/") if p]
                service = f"{parts[-2]}-{tail}" if len(parts) >= 2 else tail
            if not region:
                region = _region_from_path(op_path)

    if not service:
        raise ValueError(f"unrecognized trigger: no service derivable from "
                         f"method {method!r} resource {resource_name!r}")

    ref_basis = "insert_id"
    if not ref:
        # Some pipelines strip insertId (bare replayed entries); the
        # lifecycle still needs a deterministic correlation handle for
        # dedupe and deferred checks. Synthesized from platform fields
        # only — and since the agent arms the RECORDER-returned
        # unique_id, a synthesized ref round-trips through
        # defer_verification unchanged. The derived service is part of
        # the basis: two bare events for DIFFERENT targets (e.g. two
        # reasoningEngines under the same bare parent resourceName) must
        # not share a ref — that would hard-fail the second forever via
        # the correlation-collision guard. Caveat: without a timestamp,
        # two identical method+resource+service events share a ref and
        # are treated as one redelivered rollout.
        basis = "|".join((str(event.get("logName", "")), method,
                          resource_name, service,
                          str(event.get("timestamp", ""))))
        ref = "synth-" + hashlib.sha256(basis.encode()).hexdigest()[:24]
        ref_basis = "synthesized"

    deploy_event = {
        **({"identity_basis": "request"}
           if family in ("saas-rollout", "saas-unit-operation") else {}),
        "type": "deployment_completed",
        "service": service,
        "project": project,
        "from_revision": "",
        "to_revision": to_revision,
        "image_digest": image,
        "strategy": strategy,
        "change_classes": change_classes,
        "external_ref": ref,
        "at": str(event.get("timestamp", "")),
        # Provenance pointer, authoritative fields only — the full raw
        # entry stays in Cloud Logging, addressed by insert_id.
        "trigger": {
            "family": family,
            "api": api,
            "method": method,
            "resource": resource_name,
            "log_name": str(event.get("logName", "")),
            "insert_id": ref,
            "ref_basis": ref_basis,
            "timestamp": str(event.get("timestamp", "")),
            **({"cluster": str(labels.get("cluster_name", ""))}
               if labels.get("cluster_name") else {}),
        },
    }
    if region:
        deploy_event["region"] = region
    return deploy_event
