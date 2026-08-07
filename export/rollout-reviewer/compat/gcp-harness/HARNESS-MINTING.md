# Harness-layer envelope minting — signed envelopes over run_command output

Your agent reaches observability two ways: the reviewer's typed tools
(`rr observe …` → gcp-observe, already enveloped) and free-hand commands
(`gcloud`, `kubectl`) through the sandbox execution server's `POST /run`.
This addon seals the second path: the **sandbox server itself** wraps
every command result in a signed observation envelope before the model
ever sees it. The model can still choose what to run — it can no longer
alter what came back without breaking the seal.

**What the envelope attests:** "this exact command, in this workdir, at
this time, produced these bytes" (command + workdir live inside the
signed scope; output integrity via content hash; freshness via
`fresh_until`). **What it does not attest:** that the command was a
trustworthy evidence channel — see Evidence tiers below.

## The patch (3 lines in your sandbox server)

Your `sandbox_server.py` (the `BaseHTTPRequestHandler` on :5001) builds
a `resp` dict and then writes it. Add:

```python
# with the other imports at the top of the file:
sys.path.append("/opt/rollout-reviewer/compat/gcp-harness")
import sandbox_envelope
```

and in `do_POST`, immediately before `self.send_response(status)`:

```python
     resp = sandbox_envelope.attach(resp, cmd_list, workdir)
```

That's all. `attach()` is additive and fail-open: the existing
`returncode`/`stdout`/`stderr` fields are untouched (your agent
framework keeps parsing them unchanged), a new `observation_envelope`
field appears alongside them, and any minting error attaches
`observation_envelope_error` instead of ever failing the request.
Timeout responses (your 408 path) get envelopes with
`quality.completeness: INCOMPLETE`; output beyond
`OBS_MINT_MAX_BYTES` (default 256 KiB per stream) is clipped and marked
`TRUNCATED`; the 500 error path is left alone. The signer module is the
one already shipped in the image
(`/opt/rollout-reviewer/servers/gcp-observe/envelope.py`) — no third
copy of the signing logic to keep in sync.

Prove it locally before building the image:

```bash
python3 /opt/rollout-reviewer/compat/gcp-harness/test-sandbox-minting.py
# 9 PASS lines: mint -> verify by the rollout-intel twin -> tampered
# stdout and tampered command scope both rejected
```

## Key handling — read this part carefully

The sandbox server signs with `OBS_SIGNING_KEY`, the same key
rollout-intel verifies with. Set one non-default value for the
container (the dev default works for testing). Now the honest threat
model:

- **What this buys you:** the model cannot tamper in-band. Nothing in
  the model's context can produce or modify a valid envelope; every
  number it cites either matches a sealed payload or doesn't.
- **The residual risk:** agent commands execute in the same container
  as the signer, so a determined agent could try to *read the key*
  (`env`, `/proc/*/environ`) and mint offline. Two mitigations: first,
  such an attempt is a glaring, auditable command in the trace — the
  scorer's trust-boundary and provenance rubrics, and any human reading
  the episode, will see the reviewer running `env | grep KEY` — so the
  scheme is tamper-EVIDENT even where the container makes it not
  tamper-PROOF. Second, for hard isolation move the reviewer servers to
  the sidecar (`../docker/docker-compose.sidecar.yml`) and give only
  the sidecar the production key; the sandbox then keeps a separate
  minting key that rollout-intel is told to accept for
  `command_output` envelopes only.

## Evidence tiers — don't let flexibility dilute the floor

A sealed envelope proves the pipe, not the source. `cat` of an
agent-writable file yields a perfectly signed envelope around laundered
content. Keep two tiers:

1. **Policy-grade:** the standard signed bundle (`run_stage_checks`)
   and typed gcp-observe observations. Policy rules are satisfied ONLY
   by these. Unchanged.
2. **Corroborating:** `command_output` envelopes. The record may cite
   them as observations and reviewers can trust their integrity — but
   consumers judge the channel from `scope.command` (a `gcloud … list`
   under viewer credentials is a vetted read; a `cat /workspace/…` is
   the agent quoting itself).

The agent-facing rule for this lives in HARNESS-ADDENDUM.md — when a
command result carries an envelope, the envelope (not the model's
retelling of stdout) is the citable evidence unit.
