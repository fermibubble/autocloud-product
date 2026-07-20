"""Read-only GCP observability MCP server for AutoCloud agents.

Security shape: this process holds the credentials (Application Default
Credentials or GOOGLE_APPLICATION_CREDENTIALS), and agents call it over
MCP — the token never enters a sandbox, a prompt, or the event log. Every
tool is read-only by construction: this server contains no mutating verbs
at all, so the "read-only autonomy mode" of the product doc is a property
of the surface, not a promise in a prompt.

Requires the caller's GCP project to have granted the ADC identity:
roles/monitoring.viewer, roles/logging.viewer, roles/cloudasset.viewer
(and roles/container.viewer for GKE workloads).

Run:  GCP_PROJECT=my-project uv run --project . python server.py --port 7600
"""

import argparse
import json
import os
import time

import google.auth
import google.auth.transport.requests
import httpx
from mcp.server.fastmcp import FastMCP

PROJECT = os.environ.get("GCP_PROJECT", "")


def _token() -> str:
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _get(url: str, params: dict | None = None) -> dict:
    resp = httpx.get(
        url, params=params, headers={"Authorization": f"Bearer {_token()}"}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def _post(url: str, body: dict) -> dict:
    resp = httpx.post(
        url, json=body, headers={"Authorization": f"Bearer {_token()}"}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def build() -> FastMCP:
    mcp = FastMCP("gcp-observe", host="127.0.0.1", port=ARGS.port)

    @mcp.tool()
    def list_assets(asset_types: str = "") -> str:
        """Inventory GCP resources in the project via Cloud Asset API.
        asset_types: optional comma-separated filter, e.g.
        'container.googleapis.com/Cluster,run.googleapis.com/Service'."""
        params: dict = {"pageSize": 50}
        if asset_types:
            params["assetTypes"] = asset_types.split(",")
        out = _get(
            f"https://cloudasset.googleapis.com/v1/projects/{PROJECT}/assets", params
        )
        assets = [
            {"name": a.get("name"), "type": a.get("assetType")}
            for a in out.get("assets", [])
        ]
        return json.dumps(assets)

    @mcp.tool()
    def query_metric(metric_type: str, minutes: int = 30) -> str:
        """Time series for a Cloud Monitoring metric over the last N minutes.
        e.g. metric_type='run.googleapis.com/request_latencies' or
        'kubernetes.io/container/memory/used_bytes'."""
        now = int(time.time())
        out = _get(
            f"https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries",
            {
                "filter": f'metric.type = "{metric_type}"',
                "interval.endTime": f"{now}",
                "interval.startTime": f"{now - minutes * 60}",
                "view": "FULL",
                "pageSize": 20,
            },
        )
        return json.dumps(out.get("timeSeries", []))[:8000]

    @mcp.tool()
    def search_logs(query: str, minutes: int = 30, limit: int = 20) -> str:
        """Search Cloud Logging entries with a standard logging filter, e.g.
        'severity>=ERROR AND resource.type="cloud_run_revision"'."""
        out = _post(
            "https://logging.googleapis.com/v2/entries:list",
            {
                "resourceNames": [f"projects/{PROJECT}"],
                "filter": f"{query} AND timestamp>=\"{_iso_ago(minutes)}\"",
                "orderBy": "timestamp desc",
                "pageSize": limit,
            },
        )
        entries = [
            {
                "ts": e.get("timestamp"),
                "severity": e.get("severity"),
                "text": (e.get("textPayload") or json.dumps(e.get("jsonPayload", {})))[:300],
            }
            for e in out.get("entries", [])
        ]
        return json.dumps(entries)

    @mcp.tool()
    def list_services() -> str:
        """Cloud Run services in the project (name, region, latest revision,
        traffic split) — the rollout-review surface."""
        out = _get(
            f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/-/services"
        )
        services = [
            {
                "name": s.get("name"),
                "uri": s.get("uri"),
                "latestReadyRevision": s.get("latestReadyRevision"),
                "traffic": s.get("traffic"),
                "updateTime": s.get("updateTime"),
            }
            for s in out.get("services", [])
        ]
        return json.dumps(services)

    @mcp.tool()
    def get_recommendations(recommender: str = "google.compute.instance.IdleResourceRecommender") -> str:
        """Cost/rightsizing recommendations from the Recommender API — the
        Optimize agent's raw material. Common recommenders:
        google.compute.instance.IdleResourceRecommender,
        google.compute.instance.MachineTypeRecommender."""
        out = _get(
            f"https://recommender.googleapis.com/v1/projects/{PROJECT}"
            f"/locations/global/recommenders/{recommender}/recommendations"
        )
        return json.dumps(out.get("recommendations", []))[:8000]

    return mcp


def _iso_ago(minutes: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - minutes * 60))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7600)
    ARGS = ap.parse_args()
    if not PROJECT:
        raise SystemExit("set GCP_PROJECT (and provide ADC) before starting")
    print(f"gcp-observe: project={PROJECT} mcp=:{ARGS.port} (read-only surface)")
    build().run(transport="streamable-http")
