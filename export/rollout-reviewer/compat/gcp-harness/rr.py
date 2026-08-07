#!/usr/bin/env python3
"""rr - the rollout reviewer CLI bridge for run_command-style harnesses.

The AutoCloud sandbox executes agent commands via its /run endpoint
(sandbox_server.py), so the reviewer's whole tool surface is exposed as
ONE executable: the agent calls `rr <subcommand> ...` through its
existing run_command / sandbox_run_command tool - no ADK/Jetski tool
development required. JSON on stdout; MCP tool errors (policy_conflict,
scope_mismatch, ...) print to stderr and exit 1.

Invoke via the sibling `rr` wrapper (which supplies the python env), or:
  uv run --project <export>/servers/rollout-intel python rr.py ...

Subcommands (core review loop):
  context  EPISODE [STAGE]                   get_context_pack
  checks   EPISODE STAGE                     run_stage_checks
  record   EPISODE STAGE VERDICT --report F [--summary F|--summary-text S]
           [--next-check-minutes N --next-check-reason WHY]
  intel    TOOL [JSON_ARGS]                  any rollout-intel MCP tool
  observe  TOOL [JSON_ARGS]                  any gcp-observe MCP tool
Clock / lifecycle (REST):
  new-episode  --service S [--project P --region R --from-revision A
               --to-revision B --strategy canary --change-class C ...]
  open-checkpoint EPISODE STAGE [--session-id ID]
  outcome  EPISODE --horizon H [--final-label L]     (H: policy horizon | final)
           [--slo JSON] [--rollback-detected] [--source human|webhook|collector]
  episode  EPISODE                           full episode state

Environment: RR_INTEL_MCP, RR_OBSERVE_MCP, RR_INTEL_REST (defaults:
http://127.0.0.1:7610/mcp, http://127.0.0.1:7600/mcp, http://127.0.0.1:7611).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request

INTEL_MCP = os.environ.get("RR_INTEL_MCP", "http://127.0.0.1:7610/mcp")
OBSERVE_MCP = os.environ.get("RR_OBSERVE_MCP", "http://127.0.0.1:7600/mcp")
INTEL_REST = os.environ.get("RR_INTEL_REST", "http://127.0.0.1:7611")


def mcp_call(url: str, tool: str, args: dict):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _call():
        async with streamablehttp_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, args)
                return "".join(c.text for c in result.content if getattr(c, "text", None))

    text = asyncio.run(_call())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def rest(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{INTEL_REST}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return json.loads(resp.read())


def emit(payload) -> int:
    if isinstance(payload, str):
        # Some MCP tool errors arrive as plain strings
        print(payload, file=sys.stderr)
        return 1
    if isinstance(payload, dict) and "error" in payload:
        # Recorder rejections (policy_conflict, scope_mismatch, conflict)
        # arrive as {"error": "...", ...context...} - fail loudly so the
        # calling harness sees a nonzero exit, with context on stderr.
        print(payload["error"], file=sys.stderr)
        context = {k: v for k, v in payload.items() if k != "error"}
        if context:
            print(json.dumps(context, indent=1), file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="rr", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("context"); p.add_argument("episode"); p.add_argument("stage", nargs="?", default="")
    p = sub.add_parser("checks"); p.add_argument("episode"); p.add_argument("stage")
    p = sub.add_parser("record")
    p.add_argument("episode"); p.add_argument("stage"); p.add_argument("verdict")
    p.add_argument("--report", required=True, help="path to report_md (embeds the epistemic record)")
    p.add_argument("--summary", help="path to reasoning_summary file")
    p.add_argument("--summary-text", help="reasoning_summary inline")
    p.add_argument("--next-check-minutes", type=float, default=0,
                   help="PROPOSE the next check time (tighten honored to policy "
                        "min_interval; loosen clamped to max_interval)")
    p.add_argument("--next-check-reason", default="",
                   help="evidence behind the proposal (e.g. sample arithmetic)")
    p = sub.add_parser("intel"); p.add_argument("tool"); p.add_argument("json_args", nargs="?", default="{}")
    p = sub.add_parser("observe"); p.add_argument("tool"); p.add_argument("json_args", nargs="?", default="{}")
    p = sub.add_parser("new-episode")
    p.add_argument("--service", required=True); p.add_argument("--project", default="")
    p.add_argument("--region", default=""); p.add_argument("--from-revision", default="")
    p.add_argument("--to-revision", required=True); p.add_argument("--strategy", default="canary")
    p.add_argument("--image-digest", default=""); p.add_argument("--change-class", action="append", default=[])
    p = sub.add_parser("open-checkpoint")
    p.add_argument("episode"); p.add_argument("stage"); p.add_argument("--session-id", default="")
    p = sub.add_parser("outcome")
    p.add_argument("episode"); p.add_argument("--horizon", required=True,
                   help="a policy outcome_horizon (e.g. 30m, 2h, 24h, 7d) or 'final'")
    p.add_argument("--final-label", choices=["healthy", "regressed", "rolled_back"])
    p.add_argument("--slo", default="{}"); p.add_argument("--rollback-detected", action="store_true")
    p.add_argument("--source", default="webhook", choices=["collector", "webhook", "human"])
    p = sub.add_parser("episode"); p.add_argument("episode")

    a = ap.parse_args()

    if a.cmd == "context":
        return emit(mcp_call(INTEL_MCP, "get_context_pack", {"episode_id": a.episode, "stage": a.stage}))
    if a.cmd == "checks":
        return emit(mcp_call(INTEL_MCP, "run_stage_checks", {"episode_or_service": a.episode, "stage": a.stage}))
    if a.cmd == "record":
        summary = a.summary_text or (open(a.summary).read().strip() if a.summary else "")
        if not summary:
            print("error: provide --summary FILE or --summary-text", file=sys.stderr)
            return 2
        return emit(mcp_call(INTEL_MCP, "record_checkpoint", {
            "episode_or_service": a.episode, "stage": a.stage, "stage_verdict": a.verdict,
            "reasoning_summary": summary, "report_md": open(a.report).read(),
            "next_check_proposal_minutes": a.next_check_minutes,
            "next_check_reason": a.next_check_reason}))
    if a.cmd == "intel":
        return emit(mcp_call(INTEL_MCP, a.tool, json.loads(a.json_args)))
    if a.cmd == "observe":
        return emit(mcp_call(OBSERVE_MCP, a.tool, json.loads(a.json_args)))
    if a.cmd == "new-episode":
        return emit(rest("POST", "/intel/episodes", {
            "type": "deployment_completed", "service": a.service, "project": a.project,
            "region": a.region, "from_revision": a.from_revision, "to_revision": a.to_revision,
            "image_digest": a.image_digest, "strategy": a.strategy,
            "change_classes": a.change_class or ["application_binary"], "at": time.time()}))
    if a.cmd == "open-checkpoint":
        return emit(rest("POST", f"/intel/episodes/{a.episode}/checkpoints",
                         {"stage": a.stage, "session_id": a.session_id}))
    if a.cmd == "outcome":
        body = {"horizon": a.horizon, "slo": json.loads(a.slo),
                "rollback_detected": a.rollback_detected, "source": a.source}
        if a.final_label:
            body["final_label"] = a.final_label
        return emit(rest("POST", f"/intel/episodes/{a.episode}/outcome", body))
    if a.cmd == "episode":
        return emit(rest("GET", f"/intel/episodes/{a.episode}"))
    return 2


if __name__ == "__main__":
    sys.exit(main())
