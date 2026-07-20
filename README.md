# autocloud-product

Autonomous cloud operations on the Ensemble harness — four worker agents
against **real GCP**, under tenant `autocloud`. Grounded in the AutoCloud
product doc: goals with guardrails and success criteria, read-only-first
autonomy, human-in-the-loop as a spec-level dial.

## The workers

- `rollout-reviewer` — staged post-deployment validation (T+0/5/15/30
  protocol skill) against the 24h baseline; report + verdict, zero mutations.
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
