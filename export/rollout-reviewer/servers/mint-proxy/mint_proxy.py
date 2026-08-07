"""Minting MCP proxy — signed observation envelopes over ANY MCP server.

Bring-your-own-observability, pattern 1: the agent connects HERE instead
of directly to the upstream MCP server (Datadog, Prometheus, an internal
one — anything speaking streamable-http MCP). The proxy forwards
tools/list verbatim, forwards every tools/call upstream, and seals each
result in a signed observation envelope (type ``mcp_tool_output``)
BEFORE the model ever sees it. The upstream server is not modified.

What the envelope attests: "tool T on server S, called with args A at
time t, returned exactly this payload." It does NOT attest that the
upstream server is honest — a malicious server produces perfectly
sealed lies. Trust grading of the source stays with the consumer
(see README.md: these envelopes are corroborating-tier evidence; policy
rules remain satisfiable only by typed observations).

Integrity note: the envelope signature covers scope + content hash, so
everything that must be tamper-evident lives there — including the
completeness attestation (scope.completeness). The unsigned ``quality``
and ``source`` fields are informational; consumers trust scope.server,
never the bare source string.

Config (env):
  UPSTREAM_MCP_URL      required, e.g. http://127.0.0.1:7600/mcp
  SOURCE_ID             names the source in scope.server (default byo-mcp)
  MINT_TTL_SECONDS      freshness horizon (default 600)
  MINT_MAX_BYTES        result clip per call before minting (default 256 KiB)
  RR_ENVELOPE_PY        signer module (default ../gcp-observe/envelope.py)
  OBS_SIGNING_KEY       read by the signer — same key rollout-intel verifies

Run:
  UPSTREAM_MCP_URL=http://127.0.0.1:7600/mcp SOURCE_ID=my-observability \
    uv run --project . python mint_proxy.py --port 7630
"""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import pathlib

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

import mcp.types as types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

UPSTREAM = os.environ.get("UPSTREAM_MCP_URL", "")
SOURCE_ID = os.environ.get("SOURCE_ID", "byo-mcp")
TTL = int(os.environ.get("MINT_TTL_SECONDS", "600"))
MAX_BYTES = int(os.environ.get("MINT_MAX_BYTES", "262144"))
ARGS_MAX_BYTES = int(os.environ.get("MINT_ARGS_MAX_BYTES", "16384"))
_ENVELOPE_PY = os.environ.get(
    "RR_ENVELOPE_PY",
    str(pathlib.Path(__file__).resolve().parent.parent / "gcp-observe" / "envelope.py"),
)

_ADDENDUM = (
    "\n\n[mint-proxy] The result arrives as a SIGNED observation envelope "
    "(type mcp_tool_output); the upstream payload is inside "
    "envelope.payload.result. Cite envelope.observation_id in "
    "evidence_refs and carry the envelope verbatim."
)


def _load_signer():
    spec = importlib.util.spec_from_file_location("rr_envelope", _ENVELOPE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


envelope = _load_signer()


def _unwrap(exc: BaseException) -> BaseException:
    """anyio wraps transport failures in ExceptionGroups; find the leaf."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


async def _upstream_list() -> list[types.Tool]:
    try:
        async with streamablehttp_client(UPSTREAM) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return (await session.list_tools()).tools
    except BaseException as exc:
        leaf = _unwrap(exc)
        raise RuntimeError(
            f"mint-proxy: upstream {UPSTREAM} failed during tools/list: "
            f"{type(leaf).__name__}: {leaf}") from exc


async def _upstream_call(tool: str, args: dict) -> types.CallToolResult:
    try:
        async with streamablehttp_client(UPSTREAM) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, args)
    except BaseException as exc:
        leaf = _unwrap(exc)
        raise RuntimeError(
            f"mint-proxy: upstream {UPSTREAM} failed during tools/call "
            f"({tool}): {type(leaf).__name__}: {leaf}") from exc


def _reject_constant(_name: str):
    raise ValueError("NaN/Infinity are not strict JSON")


server = Server("mint-proxy")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = []
    for t in await _upstream_list():
        tools.append(types.Tool(
            name=t.name,
            title=t.title,
            description=(t.description or "") + _ADDENDUM,
            inputSchema=t.inputSchema,
            annotations=t.annotations,
            # outputSchema is deliberately not forwarded. Not cosmetic:
            # the proxy returns unstructured TextContent (the envelope),
            # so under the SDK's output validation a forwarded
            # outputSchema would fail EVERY call ("outputSchema defined
            # but no structured output returned").
        ))
    return tools


# validate_input=False: the upstream is the schema authority. Note the
# SDK still consults its tool cache per call — the first call after
# startup (and every call with a name absent from the upstream catalog)
# triggers a hidden extra tools/list round trip upstream.
@server.call_tool(validate_input=False)
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    result = await _upstream_call(name, arguments or {})

    text_blocks = [c.text for c in result.content
                   if isinstance(c, types.TextContent)]
    non_text = [c.type for c in result.content
                if not isinstance(c, types.TextContent)]
    enc = "\n".join(text_blocks).encode("utf-8", errors="replace")
    raw_bytes = len(enc)
    clipped = raw_bytes > MAX_BYTES
    # Decoding what was encoded with errors="replace" guarantees the
    # sealed text is valid, surrogate-free unicode whatever the upstream
    # emitted.
    text = (enc[:MAX_BYTES] if clipped else enc).decode("utf-8",
                                                        errors="replace")

    parsed: object = text
    # Parse only a single, unclipped text block: a clipped document is no
    # longer valid JSON, and multiple blocks joined would parse wrongly.
    # The pre-flight dumps proves the canonicalizer can re-serialize the
    # structure as STRICT json (rejects non-finite floats like 1e999,
    # lone surrogates, pathological nesting) — anything it cannot handle
    # is sealed as opaque text instead of erroring unminted.
    if not clipped and len(text_blocks) == 1:
        try:
            candidate = json.loads(text, parse_constant=_reject_constant)
            json.dumps(candidate, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=False).encode("utf-8")
            parsed = candidate
        except (json.JSONDecodeError, TypeError, ValueError,
                RecursionError, UnicodeEncodeError):
            parsed = text

    if clipped:
        completeness = "TRUNCATED"
    elif non_text:
        completeness = "PARTIAL"  # non-text content is not carried
    else:
        completeness = "COMPLETE"

    # Agent-chosen args are signed, so cap what enters the seal: above
    # ARGS_MAX_BYTES the signed scope carries a hash + preview instead
    # (the full args still went upstream unchanged).
    scope_args: object = arguments or {}
    try:
        args_canon = json.dumps(scope_args, sort_keys=True,
                                separators=(",", ":"), default=str)
        if len(args_canon.encode("utf-8")) > ARGS_MAX_BYTES:
            scope_args = {"args_clipped": True,
                          "args_sha256": hashlib.sha256(
                              args_canon.encode("utf-8")).hexdigest(),
                          "args_preview": args_canon[:1024]}
    except (TypeError, ValueError, RecursionError):
        scope_args = {"args_unserializable": True}

    env = envelope.mint(
        "mcp_tool_output",
        # scope is inside the signature: everything that must be
        # tamper-evident goes here, including the completeness
        # attestation. The quality block below repeats it for shape
        # parity with other envelopes but is NOT signed.
        scope={"server": SOURCE_ID, "upstream_url": UPSTREAM,
               "tool": name, "args": scope_args,
               "completeness": completeness, "result_bytes": raw_bytes},
        payload={"result": parsed, "is_error": bool(result.isError)},
        quality={"completeness": completeness,
                 "result_bytes": raw_bytes,
                 "text_blocks": len(text_blocks),
                 "non_text_content": non_text},
        source=SOURCE_ID,
        ttl_seconds=TTL,
    )
    return [types.TextContent(type="text", text=json.dumps(env))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7630)
    args = parser.parse_args()
    if not UPSTREAM:
        raise SystemExit("UPSTREAM_MCP_URL is required")
    if not os.environ.get("OBS_SIGNING_KEY"):
        print("WARNING: OBS_SIGNING_KEY is unset - minting with the "
              "PUBLICLY KNOWN dev key; envelopes are forgeable by anyone "
              "with this source tree. Fine for the sim, never for "
              "production.")

    # DNS-rebinding protection: without explicit settings the SDK
    # disables Host/Origin validation, letting a hostile web page on the
    # same machine reach the loopback port. Lock it to loopback origins.
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1", f"127.0.0.1:{args.port}",
                       "localhost", f"localhost:{args.port}"],
        allowed_origins=["http://127.0.0.1", f"http://127.0.0.1:{args.port}",
                         "http://localhost", f"http://localhost:{args.port}"],
    )
    manager = StreamableHTTPSessionManager(app=server, json_response=True,
                                           stateless=True,
                                           security_settings=security)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with manager.run():
            yield

    app = Starlette(routes=[Mount("/mcp", app=manager.handle_request)],
                    lifespan=lifespan)
    print(f"mint-proxy on 127.0.0.1:{args.port}/mcp -> {UPSTREAM} "
          f"(source {SOURCE_ID})")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
