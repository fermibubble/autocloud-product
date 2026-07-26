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
- `optimize-cost-drift` — FinOps sweeps via the Recommender API;
  savings-ranked findings with draft (never executed) remediations.
- `best-practices-reviewer` — design/IaC review against the governance
  skill corpus; risks/evidence/assumptions/open-questions verdicts.

Read-only is structural: `mcp-servers/gcp/` exposes no mutating verbs, and
credentials (ADC) live with that server process — never in sandboxes,
prompts, or logs.

## Layout

Each worker owns a folder under `agents/`:

    agents/<name>/
      agentspec.yaml            # the AgentSpec (variants: agentspec.scripted.yaml, agentspec.hitl.yaml)
      evals/                    # datasets (*.json — published by the bundle glob)
      evals/suite.yaml          # suite manifest for scripts/run-suite.sh (YAML on purpose: never published)
      fake-scripts/             # deterministic FakeProvider scripts, where the agent has a scripted twin
      README.md

Shared, product-level: `skills/` and `rubrics/` (referenced from specs and
suites by registry name), plus `capabilities/`, `mcp/`, `policies/`,
`catalog/`. Discovery is glob-driven from `ensemble.bundle.yaml` — registry
identity comes from each artifact's `name`, never its path. Runtime workers
find fake scripts via `FAKE_SCRIPTS_DIR` (os.pathsep-joined roots, e.g.
`agents/rollout-reviewer/fake-scripts`). Note: `ensemble apply` never
deletes, so the pre-rename agents (`optimize-agent`, `design-governance`)
and the old `autocloud-goals` dataset remain frozen in the registry.

## The skill corpus

Six curated skills, all following the same package convention: a tight
contract body (`SKILL.md`) plus on-demand playbooks under `references/`
that materialize at `/skills/<name>/references/` — the agent reads only
what the situation calls for (progressive disclosure). Authoring rules
live in `docs/SKILL_CONTRIBUTION_GUIDE.md`.

| Skill | For | Playbooks |
|---|---|---|
| `rollout-validation-protocol` @3.2.0 | rollout-reviewer | noise-isolation, scope-triage, evidence-gathering, stability-checks |
| `dossier-maintenance` @1.0.0 | rollout-reviewer | — |
| `incident-playbook` @1.1.0 | incident-manager | parallel-investigation, outage-correlation, exec-report-card |
| `finops-review` @1.1.0 | optimize-cost-drift | gce-modernization, stuck-savings |
| `architecture-review-standards` @1.0.0 | best-practices-reviewer | — (owns the review output contract) |
| `best-practices-assessor` @1.0.0 | best-practices-reviewer | 37-file archetype × product corpus + terraform-review |

The playbooks were harvested from a legacy skill corpus written for a
different agent platform — its domain judgment (noise vs regression
heuristics, investigation orchestration, modernization discipline, the
best-practices corpus) rewritten against this product's tool surface and
verdict contracts; its platform mechanics (discretionary verdicts,
self-collected CLI evidence, agent-owned state) deliberately discarded.
The full audit and adopt/discard record: `docs/SKILLS_AUDIT_REPORT.md`.
Unharvested raw material (58 generated diagnostic decision-trees, 14
product grounding files) is archived at
`../skills-legacy-archive-20260726.tar.gz` for the future
diagnostics-translation work.

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
(skill A/B through the harness one-change gate), and
`scripts/run-suite.sh <agent>` (per-agent suites from
`agents/*/evals/suite.yaml`; a suite may bind several rubrics — sessions
execute once, every rubric grades them, each against its own threshold;
judge-scored rubrics need an eval worker with ANTHROPIC_API_KEY).

## Activation (requires your GCP project)

    1. gcloud auth application-default login   # or GOOGLE_APPLICATION_CREDENTIALS
    2. grant the identity: monitoring.viewer, logging.viewer,
       cloudasset.viewer (container.viewer for GKE)
    3. GCP_PROJECT=<your-project> uv run --project mcp-servers/gcp python mcp-servers/gcp/server.py
    4. scripts/bootstrap.sh                    # autocloud token + ensemble apply
    5. deploy demo-service/ (gcloud run deploy demo-service --source demo-service/)
       then run the goal from agents/rollout-reviewer/evals/goals.json
       against rollout-reviewer

Agents run a real Claude model; the runtime worker needs ANTHROPIC_API_KEY.
Until both credentials exist, everything publishes and validates (bundle
apply is green) but sessions will fail at the first tool/model call — by
design, not silently.
