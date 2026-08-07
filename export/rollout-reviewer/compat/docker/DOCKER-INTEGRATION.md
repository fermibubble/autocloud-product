# Docker integration — dropping the export into the sandbox harness image

Written against the harness Dockerfile + `entrypoint_sandbox.sh` you run
today (ubuntu:22.04, gcloud/kubectl/terraform, Node 22 + `mcp-proxy`,
skills baked at `/skills/` → `/workspace/cloud/agents/autocloud/skills/`,
third-party skills via the `third_party_skills_ctx` build context →
`/workspace/third_party/skills/skills/`, `WORKDIR /workspace`).

## What your image already gives us (no changes needed)

| Harness fact | Why it fits |
|---|---|
| `mcp-proxy --transport streamablehttp` is your MCP pattern | Our two servers ARE streamable-http MCP natively — your agent adds `http://127.0.0.1:7610/mcp` (rollout-intel) and `http://127.0.0.1:7600/mcp` (gcp-observe) as endpoints; no proxy hop required |
| `WORKDIR /workspace` | The skill's deliverable `/workspace/rollout-report.md` lands correctly as-is |
| `third_party_skills_ctx` build context | The designed drop-in point for the skill (Option A) |
| gcloud installed | `compat/clouddeploy-to-episode.py` can consume your real `gcloud deploy` discovery output; `LIVE_GCP=1` mode can use the host's ADC |
| `uv` installed globally | Runs our servers with a uv-managed interpreter |
| Ports 8000 / 9222 / 5001 in use | Ours (7600/7601, 7610/7611, 7620/7621) do not collide |

**The one gap:** the image ships Python 3.10/3.11; our servers require
`>=3.12`. One build-time line fixes it: `uv python install 3.12` (uv
then supplies the interpreter for `uv run`/`uv sync` automatically).
The sim and the compat scripts are stdlib-only and run fine on the
image's python3.

## Option A — inject the skill only (zero image changes)

Your Dockerfile already supports this via the named build context:

```bash
docker buildx build \
  --build-context third_party_skills_ctx=/path/to/export/rollout-reviewer/skill \
  -t harness:with-trustworthy-review .
```

Result: `/third_party_skills/trustworthy-rollout-review/` →
(entrypoint copy) → `/workspace/third_party/skills/skills/trustworthy-rollout-review/`.
Point your agent's skill loader there (AGENT-CONTRACT §1). Use this
when the servers run elsewhere (another host, or Option C).

## Option B — bake the full stack into the image (recommended)

Everything on localhost inside the one container — no network binding
changes, matches how your entrypoint already composes services. Append
`Dockerfile.addon`'s lines to your Dockerfile (or keep them as a final
stage) and build with a second named context:

```bash
docker buildx build \
  --build-context third_party_skills_ctx=/path/to/export/rollout-reviewer/skill \
  --build-context rollout_reviewer=/path/to/export/rollout-reviewer \
  -t harness:with-trustworthy-review .
```

Then swap the CMD to the wrapper (also in `Dockerfile.addon`):
`entrypoint-addon.sh` starts sim + gcp-observe + rollout-intel via the
export's own `run-stack.sh`, waits for health, then `exec`s your
original `entrypoint_sandbox.sh` — Chrome/mcp-proxy behavior unchanged.
Env knobs pass through: `LIVE_GCP=1` (real GCP via the container's
ADC), `OBS_SIGNING_KEY` (set the same value for both server processes;
see the export README security notes), `INTEL_DB` (defaults to
`/workspace/rollout-reviewer-run/episode-store.db` so the episode store
survives on your workspace volume).

Build-time notes: `uv sync --frozen` uses the shipped `uv.lock` files
(network needed at build, not at runtime); `uv python install 3.12`
caches the interpreter in the image.

## Option C — sidecar container (only with host networking)

`Dockerfile.sidecar` + `docker-compose.sidecar.yml` run the stack as a
separate container. **Honest constraint:** the shipped servers bind
`127.0.0.1` (sim, REST faces, and FastMCP defaults), so a sidecar works
only where the containers share a network namespace —
`network_mode: host` (Linux) as in the sample compose, or a shared
`network_mode: "service:…"` arrangement. For cross-network sidecars you
would patch the bind addresses to `0.0.0.0` in
`sim/gcp_sim.py`, `servers/*/…service.py`, and `server.py` — a
deliberate change with security implications (the surfaces are
unauthenticated apart from envelope signing), so Option B is the
default recommendation.

## Path parity with the legacy skill

| Legacy expectation | In this container |
|---|---|
| Skills at `/workspace/cloud/agents/autocloud/skills/<name>/` | Unchanged — your first-party registry; the legacy `rollout-review` can stay there during migration |
| Legacy report path `<workspace_root>/cloud/agents/autocloud/skills/rollout-review/execution_artifacts/…` | Still writable (your entrypoint `chmod 777`s the copied registry); the trustworthy skill writes `/workspace/rollout-report.md` instead — copy onward if downstream tooling expects the old path |
| `gcloud deploy` discovery in-session | Move to your clock layer: `compat/clouddeploy-to-episode.py` (see LEGACY-COMPAT.md) |
| Chat notifications | `compat/notify-from-record.py` output piped to your existing chat tool |

## Smoke-testing inside the container

```bash
docker run --rm -it harness:with-trustworthy-review \
  bash -lc '/opt/rollout-reviewer/scripts/smoke-test.sh'
```

All seven checks passing inside your image is the port-complete signal
(same proof the export runs on any host; see the export README).
