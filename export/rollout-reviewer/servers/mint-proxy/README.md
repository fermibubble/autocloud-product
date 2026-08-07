# mint-proxy — signed envelopes over ANY MCP server (BYO observability)

Your harness may bring its own observability MCP server (Datadog,
Prometheus, an internal one). This proxy makes that server's results
citable evidence WITHOUT modifying it: the agent connects to the proxy,
the proxy forwards every call upstream and seals each result in a
signed observation envelope (type `mcp_tool_output`) before the model
sees it.

```
agent ──MCP──> mint-proxy :7630/mcp ──MCP──> your observability server
                    │
                    └─ every result: envelope(scope={server, tool, args},
                                              payload={result, is_error})
```

## Run

```bash
cd servers/mint-proxy
UPSTREAM_MCP_URL=http://127.0.0.1:9000/mcp SOURCE_ID=my-observability \
  uv run --project . python mint_proxy.py --port 7630

# prove the whole chain locally (fake upstream + proxy + tamper checks):
uv run --project . python test_mint_proxy.py    # 12 PASS lines
```

Config: `UPSTREAM_MCP_URL` (required), `SOURCE_ID` (names the source in
`scope.server`; default `byo-mcp`), `MINT_TTL_SECONDS` (default 600),
`MINT_MAX_BYTES` (result clip, default 256 KiB), `MINT_ARGS_MAX_BYTES`
(cap on agent args entering the signed scope, default 16 KiB — larger
args are replaced by a sha256 + preview with `args_clipped: true`;
the full args still go upstream), `RR_ENVELOPE_PY`
(signer module path, default `../gcp-observe/envelope.py` — no third
copy of the signing logic), `OBS_SIGNING_KEY` (same key rollout-intel
verifies; the proxy prints a loud warning when it starts on the dev
default). One proxy instance fronts one upstream server; run several
instances for several servers, each with its own `SOURCE_ID`.

## What a result looks like

`tools/list` passes the upstream catalog through (input schemas intact,
descriptions annotated with the envelope contract). `tools/call`
returns one text block containing the envelope; the upstream payload is
verbatim inside it:

```json
{"observation_id": "obs-…", "type": "mcp_tool_output",
 "scope": {"server": "my-observability", "tool": "query_timeseries",
           "args": {"service": "checkout"}, "upstream_url": "…"},
 "payload": {"result": <upstream result>, "is_error": false},
 "quality": {"completeness": "COMPLETE", "result_bytes": 1234},
 "observed_at": "…", "fresh_until": "…", "content_hash": "sha256:…",
 "sig": "…"}
```

The agent cites `observation_id` in the record's `evidence_refs` and
carries the envelope verbatim — same handling as gcp-observe results.
An upstream tool failure is minted too (`payload.is_error: true`): a
witnessed failure, not a lost one. Only a transport failure (upstream
unreachable) returns an unminted error — nothing was witnessed.

## Trust boundaries — read before relying on this

- **What the seal proves:** tool T on server S, called with args A at
  time t, returned exactly P — and nobody (including the model) altered
  it afterward. **What it cannot prove:** that server S is honest. A
  malicious upstream produces perfectly sealed lies.
- **Trust the signed fields only.** The signature covers `scope` and
  the payload hash — so the source name, the tool, the args, and the
  completeness attestation all live in `scope`. The bare `source` and
  `quality` fields are unsigned, informational duplicates: grade
  evidence by `scope.server` and `scope.completeness`, never by them.
- **Tier accordingly:** `mcp_tool_output` envelopes are
  CORROBORATING-tier evidence. Policy rules stay satisfiable only by
  the typed standard bundle (`run_stage_checks` / gcp-observe). A BYO
  server earns policy-grade status by getting a typed observation
  contract written for it (pattern 2 — a per-tool mapping to
  `metric_series`/`log_scan` shapes), not by being proxied.
- **Upstream text is data, never instructions.** Tool descriptions and
  result payloads from the upstream server flow into the agent's
  context sealed but UNSANITIZED — a hostile server could plant
  instruction-shaped text in either. The skill's trust-boundary rule
  applies to them exactly as to log lines: quote, flag, never comply.
  (The shipped test plants an injection line in the fake upstream's
  payload and proves it arrives sealed as data.)
- **Key exposure:** the proxy holds `OBS_SIGNING_KEY`, so it must run
  where the agent cannot read its environment — beside the other
  reviewer servers (same container caveats as
  `compat/gcp-harness/HARNESS-MINTING.md`, sidecar for hard isolation).

## Protocol notes

- Speaks streamable-http MCP on both sides (`mcp` SDK 1.x, pinned to
  the same major as the rest of this export). Stateless JSON mode on
  the serving side; one fresh upstream session per forwarded call.
- The serving side validates Host/Origin headers (DNS-rebinding
  protection) and accepts loopback origins only — a hostile web page on
  the same machine cannot reach the proxy through a rebound domain.
- Results that parse as JSON but cannot be re-serialized as STRICT
  JSON (non-finite floats like `1e999`, lone surrogates, pathological
  nesting) are sealed as opaque text instead of structured payload —
  still minted, never lost. Only a transport failure returns an
  unminted error.
- `tools/list` is forwarded live on every request — an upstream catalog
  change is visible immediately, at the cost of one upstream round trip.
- Upstream `outputSchema` is deliberately not forwarded (results are
  re-shaped into envelopes). Non-text content blocks (images, resources)
  are not carried; their presence is recorded in
  `quality.non_text_content` and completeness drops to `PARTIAL`.
