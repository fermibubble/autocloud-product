# Legacy `rollout-review` Skill — Deep Critique and Disposition

**What this is.** The full analysis of the legacy `rollout-review`
skill (formerly at `skills-legacy/rollout-review/`) and its
`context-gatherer` sub-skill tree — its implementation, its strengths
and weaknesses concept by concept, and the adopt/adapt/discard
disposition that produced `rollout-validation-protocol@3.2.0`.

**Provenance note.** The legacy source was deleted from the working
tree after the harvest completed (it was never committed to this repo),
so this document is the durable record of that analysis. The summary
verdicts also appear compressed in
[SKILLS_AUDIT_REPORT.md](SKILLS_AUDIT_REPORT.md); the harvested content
itself lives on in
[skills/rollout-validation-protocol/](../skills/rollout-validation-protocol/).

---

## 1. What it was

A 556-line `SKILL.md` implementing an eight-step rollout review
protocol, plus a two-level package: the main skill as a thin-ish
dispatcher, with a `context-gatherer` sub-skill tree of on-demand
reference files (`insight_context.md`, `alert_context.md`,
`source_code_context.md`, `app_topology_context.md`) and fourteen
product-conditional `grounding/*.txt` files loaded per GCP product.

The protocol's steps, roughly: (1) scope the target and attribute
evidence; (2, 4) query baseline and post-deploy metrics; (3) verify the
change itself landed (config intent: seccomp, env, CPU); (5) classify
errors against a noise taxonomy; (6) run later-checkpoint stability
heuristics with promote/hold reasoning; (7–8) write a report with a
causal chain and a draft remediation. Verdicts came from a
SUCCESS/FAILURE/DEGRADED/ONGOING vocabulary (plus SOAKING, PAUSED,
PENDING), state persisted in an agent-owned `state.json` keyed by log
`insertId`s, and the skill self-scheduled follow-ups via a
`defer_verification` tool on a 10-minute watch, reporting through
`send_google_chat_message` under a "never ask permission" instruction.

## 2. The verdict in one paragraph

**Its domain concepts are strong; its systems concepts are weak —
and weak precisely where Ensemble is strong.** Whoever wrote this
skill had reviewed real rollouts: the noise taxonomy, the window
hygiene, the stability heuristics, and the causal-chain report format
are operator scar tissue of real value, and nearly all of it was worth
harvesting. But every systems-level decision — discretionary verdicts
with no epistemic state, self-collected evidence with no trust
boundary, agent-owned state files, a self-scheduled lifecycle — hands
the model authority that a platform should hold. The two-level
progressive-disclosure *structure* was natively Ensemble-shaped (thin
contract + on-demand playbooks); only its cross-skill `../` binding was
broken, since relative links across skills are unversioned and
unenforced, while intra-package references are fully supported.

## 3. Strengths — the domain concepts (all harvested)

1. **Error types over counts, with a full noise taxonomy.**
   New-in-target stack traces, internal DB errors, unhandled
   exceptions, OOM, broken-pipe, and thread-starvation are regression
   signals; stdlib 4xx "error" logging and scanner probes are noise
   signals. The single sharpest operator insight in the corpus:
   **scanner probes spike during rollouts because IP and load-balancer
   reassignment exposes fresh endpoints** — so a spike of junk traffic
   at deploy time is expected, not evidence. Paired with a
   baseline-consistency test so noise claims get tested, not assumed.
   → `references/noise-isolation.md`.
2. **Scope triage before weighing.** Attribute every piece of evidence
   to target / dependency / unrelated before it counts; never blame
   co-located neighbors; sibling stages of the same release (shared
   `release_id`) are context, not the target's regression.
   → `references/scope-triage.md`.
3. **Window hygiene.** Separate, non-overlapping baseline and target
   metric queries — combined queries truncate and hide anomalies — plus
   awareness that a subsequent rollout truncates your target window.
   → `references/evidence-gathering.md`.
4. **The three-query log pattern** (from `insight_context.md`):
   severity>=ERROR, audit events, and targeted keywords (OOM, timeout,
   broken pipe); broad-then-narrow; a 7-day recency check.
   → `references/evidence-gathering.md`.
5. **Manifest over raw data.** Bulk evidence goes to workspace files;
   small manifest summaries go into context. Context-window discipline
   stated as a rule rather than left to model judgment.
   → `references/evidence-gathering.md`.
6. **Stale-status caution** (the "Audit Log Discrepancy" callout). The
   triggering event's status may be stale because controller loops are
   asynchronous — trust the fresh evidence bundle over any status in
   the goal text. This generalizes to the deception discipline our
   eval scenarios now test (`PLATFORM_SUCCESS_DECEIVED` in the rubrics
   audit; the `rollout-status-deception` dataset).
   → `references/evidence-gathering.md`.
7. **Later-checkpoint stability heuristics.** Linear upward memory or
   connection trends as leak suspicion — we added the refinement that
   early linear growth is often cache/JIT/autoscaler warmup, so ask
   "does it plateau"; restart/crash recurrence; slow-burn error creep;
   explicit promote/hold reasoning at the final check-in.
   → `references/stability-checks.md`.
8. **The three-level causal chain** — root cause → first-order effect →
   observed symptoms — with the honest property that an unfillable
   chain exposes a symptoms-only claim. Plus the draft-remediation
   template (Goal / Success criteria / Guardrails & risks), drafted
   for a human and never executed. → the 3.2.0 report format.
9. **"Success is a durability claim."** The deepest single idea in the
   skill: convergence is not success, and a verdict at deploy time is
   a prediction, not a fact. The legacy implementation (self-scheduled
   10-minute watch) was wrong, but the concept is why our T+0/5/15/30
   ladder and 30m/2h/24h outcome labels exist at all.

## 4. Weaknesses — the systems concepts (all discarded, with reasons)

| Discarded | Why |
|---|---|
| SUCCESS/FAILURE/DEGRADED/ONGOING (+ SOAKING/PAUSED/PENDING) verdicts | No epistemic state — "I don't know" is not expressible, so thin evidence gets rounded to a confident word. The recorder enforces `healthy \| regression-suspected \| insufficient-evidence` instead. |
| Self-declared success, agent-discretion verdicts | No deterministic floor; eloquence could argue any outcome. Our tighten-only recorder makes the model's eloquence structurally irrelevant to the floor. |
| `state.json` + log-`insertId` identity | Agent-owned mutable state with no owner, no versioning, no conflict policy — the exact P3 failure. rollout-intel's append-only episode store owns durable state; log-line IDs are not rollout identities. |
| `defer_verification` + 10-minute self-scheduled watch | The agent owned its own clock and lifecycle. The relay owns the clock; one checkpoint per session. |
| `send_google_chat_message` + "never ask permission" | The tool did not exist on any surface, and autonomy posture belongs in the spec, not the prose. Comms are a platform concern (autonomy Gate A, when earned). |
| Mandatory self-collected gcloud/kubectl evidence | Self-collected, unauthenticated evidence violates the signed-envelope trust rule and is a prompt-injection surface; the sandbox has no CLI and no egress by design. |
| google3 report path + "Evaluation Trace Metadata" step indices | Environment leakage from the original eval harness — step indices in the report format are fabrication bait. The rubric expects `/workspace/rollout-report.md`. |
| Mermaid component diagram in the report | Decoration, not evidence. |
| Cross-skill `../` relative links as composition | Unversioned and unenforced — a silent-drift channel. Intra-package references plus registry refs replace it. |
| `alert_context.md`, `source_code_context.md`, `app_topology_context.md` | Wrong trigger shape (incident-manager's problem, not the reviewer's), no repo/storage access on the surface, no topology surface (that gap is G3). |

The pattern across all ten: **every discard is a place where the skill
asked the model to hold something a platform should hold** — a verdict
floor, a trust boundary, durable state, a clock, an authority posture.
That is not a criticism of the author; without a platform, prose is
the only place to put those things. It is the argument for the
platform.

## 5. The sub-skill tree

`context-gatherer` was the legacy package's progressive-disclosure
layer, and its structure — a thin dispatcher loading reference files on
demand — is exactly the package convention Ensemble skills use. Of its
contents: `insight_context.md` carried the three-query log pattern and
was harvested; the fourteen `grounding/*.txt` product files
(product-conditional GCP knowledge) were parked as a future shared
`gcp-product-grounding` skill once mutating commands are stripped —
useful to both the reviewer and incident-manager; the other three
context files were discarded per the table above.

## 6. What was adapted rather than copied

- **Post-convergence durability** → embodied by the relay-owned
  checkpoint ladder plus outcome labels; only the what-to-look-for
  heuristics were carried as prose.
- **Product-conditional grounding** → future `gcp-product-grounding`
  shared skill.
- **Multi-target release awareness** → the sibling-stage sentence
  survives in scope-triage; the real fix is release linkage as episode
  data (gap G7), not skill prose.
- **Config-intent validation** (Step 3: did the change itself land —
  seccomp, env, CPU) → impossible on today's read surface
  (`list_assets` is name/type only); recorded as the config-read
  roadmap item under gap G3. The legacy skill was *right* to want
  this.

## 7. What landed

`rollout-validation-protocol@3.2.0`: the contract body kept verbatim
(steps, verdict vocabulary, trust rules), one new compact
"interpretation playbooks" section carrying two inline invariants —
interpretation may only tighten, never loosen (noise reasoning can
prevent an unnecessary tighten and inform the narrative, but never
converts a policy fail into healthy), and error types over counts —
plus a when-to-read index into four bundled playbooks:

| Playbook | Harvested concepts |
|---|---|
| `references/noise-isolation.md` | Noise taxonomy, scanner/IP-LB insight, baseline-consistency test, quantified partitioning |
| `references/scope-triage.md` | Target/dependency/unrelated attribution, sibling-release context |
| `references/evidence-gathering.md` | Window hygiene, three-query pattern, 7-day recency, manifest discipline, stale-status caution |
| `references/stability-checks.md` | Leak trends with the plateau/warmup refinement, restart recurrence, slow-burn creep, promote/hold reasoning |

The report format gained the causal chain and the draft-remediation
section. En route, the harvest also surfaced and fixed the
`query_metrics` → `query_metric` drift family across the skill, the
observability capability (bumped to 1.0.1), and both gcp-observe
server manifests. Both reviewer specs (live and scripted twin) bumped
to the new skill in lockstep, keeping the model section the twin's
only diff.

The same harvest pattern was then applied to the other three agents
(incident-playbook@1.1.0, finops-review@1.1.0, and the
best-practices-assessor@1.0.0 fork) — this document covers only the
rollout-review analysis that established the pattern.

---

**Postscript (2026-08-01).** The archived skill this document analyzes has
returned to the tree — deliberately, and unchanged — as
`skills/legacy-rollout-review-baseline/SKILL.md` (`@0.0.0`): the pinned
baseline arm for paired evaluation against `trustworthy-rollout-review@1.0.0`.
The intake contract (frontmatter quarantine + a compatibility shim appended
after the verbatim body) is documented in that file and in the audit report's
addendum. Every weakness this critique catalogs is now a measurable delta
rather than a remembered one: the comparison protocol is
`scripts/baseline-vs-trustworthy.sh`.
