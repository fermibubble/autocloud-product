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
The sim-stack processes and their ports: gcp_sim (GCP API :7620, world
face :7621), gcp-observe sim mode (MCP :7600, bundle REST :7601),
rollout-intel (MCP :7610, REST :7611), probe target (:7640,
`sim/probe_target.py`), fastforward (MCP :7630, REST :7631), plus the
relay and the outcome collector.
Verification, all key-free, all green: `scripts/golden-rollout.sh`
(verdicts vs world truth, dynamic ladder lengths, all evidence signed;
with `FF_API` set it also requires a verified `no_material_temporal_hazard`
Fast-Forward envelope at every legacy T+30),
`scripts/dossier-golden.sh` (governed writes → projection → topic-prefix
isolation → as_of time travel → live session reading the `/memory`
mount), `scripts/replay-run.sh` (time-correct replay, false-safe
weighted 10x), `scripts/learning-golden.sh` (recurrence threshold,
contradiction blocking, human promotion), `scripts/experiment-run.sh`
(skill A/B through the harness one-change gate),
`scripts/ff-golden.sh` (seeded delayed faults blocked at T+30 by verified
temporal counterexamples, healthy control unblocked, scaled-24h labels
confirm recall 3/3), `scripts/ff-replay.sh` (byte-identical temporal
findings across two identical seeded runs), `scripts/ff-arms.sh`
(signal-only vs full-escalation arm comparison),
`scripts/ff-seed-profiles.sh` (Fast-Forward temporal profile seeding), and
`scripts/run-suite.sh <agent>` (per-agent suites from
`agents/*/evals/suite.yaml`; a suite may bind several rubrics — sessions
execute once, every rubric grades them, each against its own threshold;
judge-scored rubrics need an eval worker with ANTHROPIC_API_KEY).

## Fast-Forward (`fastforward/`)

Test the cliff, not the whole road: the delayed rollout failures that
hurt most are not "more minutes of the same telemetry" but a boundary
crossing — handle exhaustion, retry amplification, credential expiry
after key rotation — that the T+0..T+30 ladder window never shows.
Fast-Forward compiles each deploy's change manifest into typed temporal
hazards (`resource_lifecycle`, `rate_balance`, `clock_expiry`,
`state_boundary`, `concurrency`, `agent_longevity`) and escalates
**Signal → Probe**: cheap counter/slope projection first, then — only
where a hazard warrants it — deterministic probe runs against an isolated
probe-target instance advanced along non-wall-clock age axes (cycles,
requests, rotations, credential age). Every request lands in a closed
outcome vocabulary — `temporal_counterexample | bounded_future_envelope |
projected_boundary | unsupported_temporal_risk |
no_material_temporal_hazard | inconclusive_budget` — and results are
minted as **signed observation envelopes** (source `rollout-fastforward`)
that the T+30 policy rule (`temporal-evidence`, `rollout-slo.yaml`
version 2) consumes: `temporal_counterexample` fails the stage;
`inconclusive_budget` and `unsupported_temporal_risk` are
insufficient-evidence and **never become a pass**; an absent or
unverified envelope is likewise insufficient — Fast-Forward can gate, but
never rubber-stamp.

The relay and rollout-intel take `FF_API` (the Fast-Forward REST base,
`http://127.0.0.1:7631`) to file FF requests at deploy time and to pull
result envelopes at T+30; without it the stack runs pre-FF behavior. The
FF service itself reads `FF_DB`, `WORLD_API`, `PROBE_API`, `OBSERVE_API`,
`OBS_SIGNING_KEY`, and `FF_MODE` (`full` | `signal_only`).
**SIM_TIME_SCALE coupling warning:** the sim world, the relay, the
outcome collector, and any golden script must all share the SAME
`SIM_TIME_SCALE` value — no endpoint broadcasts it, so a mismatch
silently desynchronizes ladder timing from ground-truth fault timing and
invalidates every time-based assertion.

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
