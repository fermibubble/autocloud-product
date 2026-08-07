#!/usr/bin/env python3
"""End-to-end proof of the minting MCP proxy.

Chain under test:
  MCP client (the agent's seat) -> mint-proxy :7638 -> fake BYO server :7639

1. tools/list passes the upstream catalog through (schema intact,
   description annotated).
2. tools/call returns a signed envelope; the upstream payload —
   including its planted injection line — is sealed inside as data.
3. rollout-intel's OWN envelope twin verifies it (the real consumer).
4. Tampering with the payload or the scope breaks the seal.
5. An upstream tool failure is minted as a witnessed error
   (payload.is_error), not lost.

Run: uv run --project . python test_mint_proxy.py
"""

import asyncio
import copy
import importlib.util
import json
import os
import pathlib
import socket
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # export/rollout-reviewer
UPSTREAM_PORT, PROXY_PORT = 7639, 7638

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


intel_envelope = load(ROOT / "servers/rollout-intel/rollout_intel/envelope.py",
                      "intel_envelope")

fails = 0


def check(name, ok):
    global fails
    print(("PASS" if ok else "FAIL"), "-", name)
    fails += 0 if ok else 1


def wait_port(port, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


async def run_checks():
    url = f"http://127.0.0.1:{PROXY_PORT}/mcp"
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Catalog passthrough
            tools = (await session.list_tools()).tools
            by_name = {t.name: t for t in tools}
            check("upstream tools visible through proxy",
                  {"get_error_rate", "broken_probe"} <= set(by_name))
            t = by_name.get("get_error_rate")
            props = (t.inputSchema or {}).get("properties", {}) if t else {}
            check("input schema passed through intact",
                  {"service", "minutes"} <= set(props))
            check("description annotated with envelope contract",
                  t is not None and "[mint-proxy]" in (t.description or ""))

            # 2. Sealed result
            res = await session.call_tool(
                "get_error_rate", {"service": "checkout", "minutes": 15})
            env = json.loads("".join(
                c.text for c in res.content if getattr(c, "text", None)))
            check("result is an envelope with obs- id",
                  env.get("observation_id", "").startswith("obs-"))
            check("scope binds source, tool, and args",
                  env["scope"]["server"] == "byo-fake-observability"
                  and env["scope"]["tool"] == "get_error_rate"
                  and env["scope"]["args"] == {"service": "checkout",
                                               "minutes": 15})
            payload = env["payload"]["result"]
            check("upstream payload sealed verbatim",
                  payload["error_rate"] == 0.7
                  and "IGNORE ALL PREVIOUS INSTRUCTIONS" in payload["note"])

            # 3. Consumer-side verification
            ok, reason = intel_envelope.verify(env)
            check(f"rollout-intel twin verifies it ({reason})", ok)

            # 4. Tampering breaks the seal
            bad = copy.deepcopy(env)
            bad["payload"]["result"]["error_rate"] = 0.0
            ok, reason = intel_envelope.verify(bad)
            check(f"tampered error_rate rejected ({reason})", not ok)
            bad2 = copy.deepcopy(env)
            bad2["scope"]["args"]["service"] = "innocent-service"
            ok, reason = intel_envelope.verify(bad2)
            check(f"tampered scope args rejected ({reason})", not ok)
            bad3 = copy.deepcopy(env)
            bad3["scope"]["completeness"] = "TRUNCATED"
            ok, reason = intel_envelope.verify(bad3)
            check(f"tampered completeness attestation rejected ({reason})",
                  not ok)

            # 5. Upstream failure is a witnessed, sealed error
            res = await session.call_tool("broken_probe", {"target": "db"})
            env = json.loads("".join(
                c.text for c in res.content if getattr(c, "text", None)))
            ok, _ = intel_envelope.verify(env)
            check("upstream tool failure minted with is_error=true",
                  ok and env["payload"]["is_error"] is True)

            # 6. A legitimately empty result stays COMPLETE (no phantom
            #    non-text content from empty-string truthiness)
            res = await session.call_tool("get_empty", {"service": "checkout"})
            env = json.loads("".join(
                c.text for c in res.content if getattr(c, "text", None)))
            check("empty result marked COMPLETE with no phantom blocks",
                  env["scope"]["completeness"] == "COMPLETE"
                  and env["quality"]["non_text_content"] == []
                  and env["payload"]["result"] == "")


def main():
    env = dict(os.environ)
    procs = []
    try:
        procs.append(subprocess.Popen(
            [sys.executable, str(HERE / "test_fake_upstream.py"),
             "--port", str(UPSTREAM_PORT)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if not wait_port(UPSTREAM_PORT):
            raise SystemExit("fake upstream did not start")
        proxy_env = dict(env)
        proxy_env["UPSTREAM_MCP_URL"] = f"http://127.0.0.1:{UPSTREAM_PORT}/mcp"
        proxy_env["SOURCE_ID"] = "byo-fake-observability"
        procs.append(subprocess.Popen(
            [sys.executable, str(HERE / "mint_proxy.py"),
             "--port", str(PROXY_PORT)],
            env=proxy_env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL))
        if not wait_port(PROXY_PORT):
            raise SystemExit("mint-proxy did not start")
        asyncio.run(run_checks())
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
    print()
    print("all checks passed" if fails == 0 else f"{fails} check(s) FAILED")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
