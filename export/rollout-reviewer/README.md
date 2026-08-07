# Rollout Reviewer — portable export

A self-contained port of the **trustworthy rollout reviewer**: the skill
(nine-principle protocol), its schema and validator, the executable tool
surface (two core servers plus an optional BYO minting proxy), a
deterministic simulator for testing, and a reference run. Copy this folder to any system with `python3 >= 3.12`,
`uv`, and `curl` — nothing here references the source repository.

## Quickstart (3 commands)

```bash
./scripts/run-stack.sh      # start sim + gcp-observe + rollout-intel
./scripts/smoke-test.sh     # prove the whole loop executes here (7 checks)
./scripts/run-stack.sh stop
```

The smoke test arms fixtures, fires a faulty deploy in the sim, gathers
signed evidence over MCP, proves the recorder rejects a softening
verdict, records a schema-valid epistemic record, and validates it —
including that the planted prompt-injection line was quoted, not obeyed.

## What's in the folder

| Path | What it is |
|---|---|
| `skill/trustworthy-rollout-review/` | The skill: `SKILL.md` (the contract your agent follows) + nine per-principle specs in `references/`. **Byte-identical** to the registry-published package |
| `schemas/` | One JSON Schema per principle (`evidence-envelope`, `proposed-action`, `quoted-evidence`, `validity-horizon`, `outcome`, …) composed by `$ref` into `epistemic-record.schema.json` — see `schemas/README.md` for the full principle→schema manifest, including which principles deliberately have no schema |
| `compat/` | **Legacy-harness compatibility**: `LEGACY-COMPAT.md` maps every tool the legacy rollout-review skill uses (gcloud discovery, chat notifications, defer_verification, state.json…) onto this export; `notify-from-record.py` renders the legacy chat formats from recorded truth; `clouddeploy-to-episode.py` bridges your gcloud deploy discovery into episode creation; `docker/` integrates with the sandbox harness image; `gcp-harness/` is the AutoCloud GCP deployment kit — `PORTING.md` (step-by-step), the `rr` CLI bridge (drive every reviewer tool through your existing run_command), `HARNESS-ADDENDUM.md` (agent-instruction mapping), `sandbox_envelope.py` + `HARNESS-MINTING.md` (harness-layer minting: a 3-line sandbox-server patch that seals every run_command result in a signed envelope), and `rubrics/` — per-principle Trustworthy Autonomy scorer rubrics, a weighted composite, and a protocol-neutral comparative rubric, in your batch scorer's template format |
| `scripts/validate-epistemic-record.py` | The record validator (self-test, file, or `--episode` over REST). Only ported file: two path constants adjusted to this layout |
| `scripts/run-stack.sh`, `scripts/smoke-test.sh` | Stack launcher and end-to-end proof |
| `scripts/build-smoke-record.py` | Builds a minimal valid record from a gather trace (smoke test only — a real agent composes its own) |
| `servers/rollout-intel/` | Policy + recorder + episode store. MCP `:7610/mcp`, REST `:7611`. Own `pyproject.toml`/`uv.lock` |
| `servers/gcp-observe/` | Evidence source; every tool result is an HMAC-signed envelope. MCP `:7600/mcp`, bundle `:7601`. Works against the sim or real GCP (`LIVE_GCP=1`) |
| `servers/mint-proxy/` | BYO-observability minting proxy: front ANY unmodified MCP server and every tool result comes back as a signed `mcp_tool_output` envelope (corroborating-tier evidence). MCP `:7630/mcp`; see its README for trust boundaries |
| `sim/` | `gcp_sim.py` (stdlib-only seeded GCP stand-in, incl. the injection drill) + `outcome_collector.py` (labels episodes from world truth; gateway-free) |
| `examples/` | A complete recorded run: session input, trace, report with epistemic record, episode state, decision audit, validator output — plus `driver/session_driver.py`, a reference MCP client your harness can copy |
| `AGENT-CONTRACT.md` | How to wire YOUR harness: instructions text, session input format, deliverable, and the clock contract |
| `TOOL-CONTRACT.md` | The tool surface: every tool's args, returns, and error cases; MCP endpoints and REST fallbacks for non-MCP harnesses |

## Coming from the legacy rollout-review skill?

Start with `compat/LEGACY-COMPAT.md`. Your existing tools survive: your
log/metric queries, your `send_google_chat_message`, your
`defer_verification` scheduler (it becomes the checkpoint clock), and
your gcloud deploy discovery (it becomes the episode feed via
`compat/clouddeploy-to-episode.py`). The compat doc gives the
tool-by-tool mapping and a three-step migration order.

## Integrating with your harness

1. **Load the skill**: give your agent `skill/trustworthy-rollout-review/SKILL.md`
   as its operating instructions (plus on-demand access to `references/`).
   `AGENT-CONTRACT.md` has the system-prompt text and session input format.
2. **Bind the tools**: if your harness speaks MCP, connect to
   `http://host:7610/mcp` and `http://host:7600/mcp` (streamable-http) —
   done. If not, `TOOL-CONTRACT.md` specifies each tool so you can bridge
   or reimplement; `examples/driver/session_driver.py` shows a complete
   MCP client in ~40 lines.
3. **Provide the clock**: one agent session per checkpoint
   (T+0/+5/+15/+30). The Ensemble relay is deliberately NOT shipped
   (gateway-bound); `AGENT-CONTRACT.md` §Clock defines the replacement:
   create episode → open checkpoint → run session → repeat.
4. **Validate outputs**: run `scripts/validate-epistemic-record.py
   --episode <id> --intel http://host:7611` after sessions; wire it into
   your eval loop.

## References inside the skill that this export does not ship

The skill is shipped byte-identical, so two prose references point at
repo files by their repo paths:

| Mentioned in the skill | In this export |
|---|---|
| `docs/product/rollout-reviewer.md` (SKILL.md, the standard) | Not shipped — the nine `references/*.md` specs are self-sufficient for execution |
| `schemas/epistemic-record.schema.json` (epistemics.md) | Shipped at `schemas/` in this folder (the validator's default already points there) |

## Security notes

- **OBS_SIGNING_KEY**: evidence envelopes are HMAC-signed at
  `servers/gcp-observe/envelope.py` and verified at
  `servers/rollout-intel/rollout_intel/envelope.py`. Both read
  `OBS_SIGNING_KEY` and default to the shared **dev key** — fine for the
  sim; in production export the *same non-default value* to **both**
  processes. The two files are twins with no shared lib: if you modify
  signing logic in one, mirror it in the other.
- **Ensemble opt-outs are automatic**: with `ENSEMBLE_TOKEN` unset (the
  default here), rollout-intel's dossier memory projection is disabled and
  the store runs journal-only. No other Ensemble coupling exists in the
  shipped code.
- The reviewer surface is read-only by construction: no mutating verbs
  exist on either MCP server.

## Running against real GCP

```bash
GCP_PROJECT=<your-project> LIVE_GCP=1 ./scripts/run-stack.sh
```

Requires Application Default Credentials on the host. The smoke test is
sim-only (its assertions depend on the sim's demo-errors scenario).
