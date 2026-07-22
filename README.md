# autocloud-product

Autonomous cloud operations on the Ensemble harness — four worker agents
against **real GCP**, under tenant `autocloud`. Grounded in the AutoCloud
product doc: goals with guardrails and success criteria, read-only-first
autonomy, human-in-the-loop as a spec-level dial.

## The workers

- `rollout-reviewer` — staged post-deployment validation: one session per
  checkpoint of a durable rollout *episode* (T+0/5/15/30 ladder, ended
  early by a governed stabilization window), against signed evidence and
  a deterministic policy the model cannot override; report + verdict
  (`healthy | regression-suspected | insufficient-evidence`), zero
  mutations. Backed by the Rollout Intelligence Layer below.
- `incident-manager` — parallel-hypothesis investigation via ceiling-clamped
  spawns; blast radius; postmortem + comms drafts. (`incident-manager-hitl`:
  identical worker, every cloud call human-approved — the autonomy dial as a
  one-section spec diff.)
- `optimize-agent` — FinOps sweeps via the Recommender API; savings-ranked
  findings with draft (never executed) remediations.
- `design-governance` — design/IaC review against the governance skill
  corpus; risks/evidence/assumptions/open-questions verdicts.

Read-only is structural: `mcp-servers/gcp/` exposes no mutating verbs, and
credentials (ADC) live with that server process — never in sandboxes,
prompts, or logs.

## The Rollout Intelligence Layer (`intel/`)

Long-term memory for the rollout reviewer, built to the "Memory Design
for the Autonomous Cloud Rollout Reviewer" research: the verdict is
always policy + live evidence, with memory informing interpretation —
never deciding.

- **Signed evidence** — every gcp-observe result is a server-minted,
  HMAC-signed observation envelope (`OBS_SIGNING_KEY` never enters a
  sandbox). rollout-intel verifies signature *and scope*: evidence for a
  different service cannot satisfy this episode's policy.
- **Deterministic policy** (`policies/rollout-slo.yaml`) — re-evaluated
  server-side at record time; a verdict contradicting it is rejected
  (`policy_conflict`). Thin evidence is `insufficient-evidence`, never
  healthy.
- **Service dossiers** — a bitemporal journal (valid time + record time,
  `as_of` reads that never resurrect expired claims) is the truth; the
  harness store `memstore://project/rollout-dossiers` is a projection of
  ACTIVE revisions, attached **read-only**: agents propose
  (hypothesized/asserted only), humans promote via `scripts/intelctl.py`.
- **Balanced precedents** — labeled episodes only, architecture-strict,
  bitemporal (`labeled_at <= as_of`), 2 healthy + 2 unhealthy by
  fingerprint similarity, never backfilled; every retrieval audited.
- **Conservative learning** — `sim/outcome_collector.py` labels episodes
  from ground truth at 30m/2h/24h horizons (never from agent verdicts;
  never overwriting a human label); promotion *suggestions* need ≥3
  episodes labeled before the proposal plus no contradiction; signal
  utility ranks which evidence actually predicted correct verdicts.

Everything above runs **without GCP credentials** against `sim/gcp_sim.py`
(a seeded, GCP-API-shaped world — only `GCP_API_BASE` swaps for prod).
Verification, all key-free, all green: `scripts/golden-rollout.sh`
(verdicts vs world truth, dynamic ladder lengths, all evidence signed),
`scripts/dossier-golden.sh` (governed writes → projection → topic-prefix
isolation → as_of time travel → live session reading the `/memory`
mount), `scripts/replay-run.sh` (time-correct replay, false-safe
weighted 10x), `scripts/learning-golden.sh` (recurrence threshold,
contradiction blocking, human promotion), `scripts/experiment-run.sh`
(skill A/B through the harness one-change gate).

## Activation (requires your GCP project)

    1. gcloud auth application-default login   # or GOOGLE_APPLICATION_CREDENTIALS
    2. grant the identity: monitoring.viewer, logging.viewer,
       cloudasset.viewer (container.viewer for GKE)
    3. GCP_PROJECT=<your-project> uv run --project mcp-servers/gcp python mcp-servers/gcp/server.py
    4. scripts/bootstrap.sh                    # autocloud token + ensemble apply
    5. deploy demo-service/ (gcloud run deploy demo-service --source demo-service/)
       then run the first goal from datasets/goals.json against rollout-reviewer

Agents run a real Claude model; the runtime worker needs ANTHROPIC_API_KEY.
Until both credentials exist, everything publishes and validates (bundle
apply is green) but sessions will fail at the first tool/model call — by
design, not silently.
