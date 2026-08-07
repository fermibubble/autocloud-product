#!/usr/bin/env python3
"""Trace-capturing driver for one trustworthy-rollout-review session.

The model in this session is the operator (Claude) following
skills/trustworthy-rollout-review/SKILL.md step by step; this driver is
the tool harness: it makes exactly the MCP calls it is told to, logs
every call and result to ../trace.jsonl, and prints results for the
agent to read between phases.

Usage:
  session_driver.py gather  <episode> <stage>   # SKILL steps 1-2 (+ P2 log partition)
  session_driver.py probe   <episode> <stage>   # deliberate softening attempt (floor demo)
  session_driver.py record  <episode> <stage> <report_file> <summary_file> <verdict>
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

RESULTS = Path(__file__).resolve().parent.parent
TRACE = RESULTS / "trace.jsonl"
INTEL_MCP = "http://127.0.0.1:7610/mcp"
OBSERVE_MCP = "http://127.0.0.1:7600/mcp"


def log(entry: dict) -> None:
    entry["ts"] = time.strftime("%H:%M:%S", time.gmtime()) + "Z"
    with TRACE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


async def call(url: str, tool: str, args: dict) -> dict | str:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            log({"type": "tool_call", "server": url, "tool": tool, "args": args})
            t0 = time.monotonic()
            result = await session.call_tool(tool, args)
            ms = round((time.monotonic() - t0) * 1000)
            text = "".join(c.text for c in result.content if getattr(c, "text", None))
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            log({"type": "tool_result", "tool": tool, "ms": ms, "result": payload})
            return payload


async def gather(episode: str, stage: str) -> None:
    log({"type": "agent_thinking", "note": f"SKILL step 1: get_context_pack for {episode} - identity, policy rules, prior verdicts, precedents, dossier."})
    ctx = await call(INTEL_MCP, "get_context_pack", {"episode_id": episode, "stage": stage})
    print("== get_context_pack =="); print(json.dumps(ctx, indent=1))
    log({"type": "agent_thinking", "note": f"SKILL step 2: run_stage_checks for {stage} - signed bundle collected server-side, deterministic policy evaluated."})
    checks = await call(INTEL_MCP, "run_stage_checks", {"episode_or_service": episode, "stage": stage})
    print("== run_stage_checks =="); print(json.dumps(checks, indent=1))
    log({"type": "agent_thinking", "note": "P2 noise discipline: partition the error window by path shape with separate queries before any noise reasoning (extra evidence; the RECORD cites only recorded bundle envelopes and policy refs - this partition informs the narrative)."})
    part_probe = await call(OBSERVE_MCP, "search_logs", {"query": "path:(/admin OR /.env OR /wp-login)", "service": "demo-errors", "minutes": 30, "limit": 10})
    part_real = await call(OBSERVE_MCP, "search_logs", {"query": "severity>=ERROR", "service": "demo-errors", "minutes": 30, "limit": 20})
    print("== partition: probe-paths =="); print(json.dumps(part_probe, indent=1))
    print("== partition: severity>=ERROR =="); print(json.dumps(part_real, indent=1))


async def probe(episode: str, stage: str) -> None:
    log({"type": "agent_thinking", "note": "DELIBERATE FLOOR PROBE (not the skill's verdict): attempt to record 'healthy' against the failing policy to demonstrate the recorder's tighten-only rejection. Expected: policy_conflict, stored for audit, checkpoint stays open."})
    res = await call(INTEL_MCP, "record_checkpoint", {
        "episode_or_service": episode, "stage": stage,
        "stage_verdict": "healthy",
        "reasoning_summary": "FLOOR PROBE - deliberately contradicts policy to demonstrate recorder rejection.",
        "report_md": "probe - not a report",
    })
    print("== floor probe result =="); print(json.dumps(res, indent=1))


async def record(episode: str, stage: str, report_file: str, summary_file: str, verdict: str) -> None:
    report = Path(report_file).read_text()
    summary = Path(summary_file).read_text().strip()
    log({"type": "agent_thinking", "note": "SKILL step 5: record_checkpoint - stage_verdict equals the record's verdict; report embeds the epistemic record; reasoning_summary is the compression contract."})
    res = await call(INTEL_MCP, "record_checkpoint", {
        "episode_or_service": episode, "stage": stage,
        "stage_verdict": verdict,
        "reasoning_summary": summary,
        "report_md": report,
    })
    print("== record_checkpoint =="); print(json.dumps(res, indent=1))
    ws = RESULTS / "workspace"
    ws.mkdir(exist_ok=True)
    (ws / "rollout-report.md").write_text(report)
    log({"type": "tool_call", "server": "builtin", "tool": "file_write", "args": {"path": "rollout-report.md", "bytes": len(report)}})
    log({"type": "tool_result", "tool": "file_write", "result": "written"})
    print(f"report written to {ws / 'rollout-report.md'}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gather":
        asyncio.run(gather(sys.argv[2], sys.argv[3]))
    elif cmd == "probe":
        asyncio.run(probe(sys.argv[2], sys.argv[3]))
    elif cmd == "record":
        asyncio.run(record(*sys.argv[2:7]))
    else:
        raise SystemExit(f"unknown command {cmd}")
