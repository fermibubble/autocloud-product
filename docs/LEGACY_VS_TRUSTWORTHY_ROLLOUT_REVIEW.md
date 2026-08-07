# Legacy Rollout Review vs Trustworthy Rollout Review

A design-level comparison of the two skills in the paired evaluation:

| | Baseline | Candidate |
|---|---|---|
| Skill | `legacy-rollout-review-baseline@0.0.0` | `trustworthy-rollout-review@1.0.0` |
| Origin | The archived pre-harvest `rollout-review` skill, preserved verbatim (plus a recording shim) | Built directly on the nine principles of trustworthy autonomy (docs/product/rollout-reviewer.md) |
| Shape | One 556-line, 8-step monolith | A ~110-line contract + nine per-principle specs (`references/*.md`, one per principle) |
| Unit of work | An open-ended, self-managed watch over a whole rollout | Exactly one checkpoint of one episode per session; the relay owns the ladder |

This document describes the *designed* differences. The *measured*
differences come from `scripts/baseline-vs-trustworthy.sh` (pre-registered
bars B1–B6 in its header); until that run completes, every claim here is a
design claim, not a result.

## The one-sentence version

The legacy skill asks the model to hold everything — the verdict floor, the
state, the clock, the trust boundary, the authority; the trustworthy skill
holds the model to nine specs and lets the platform hold the rest.

## Principle by principle

| Principle | Legacy baseline | Trustworthy candidate |
|---|---|---|
| **P1 Epistemics** | Verdict is a bare status word — `SUCCESS \| FAILURE \| DEGRADED \| ONGOING` (plus SOAKING/PAUSED/PENDING). No confidence, no unknowns, no alternatives, no "what would change this call." "I don't know" is not expressible; thin evidence rounds to a confident word | Verdict never travels as a bare label: every report embeds a machine-parseable epistemic record (observations with cited evidence, inferences with live alternatives, qualitative confidence with its basis, explicit unknowns, discriminating checks, a validity horizon), schema-validated (`schemas/epistemic-record.schema.json`); `insufficient-evidence` is a first-class outcome |
| **P2 Provenance** | Evidence is whatever the agent gathered — including self-collected `gcloud` output and numbers with no reproducible path; nothing distinguishes a measured value from a remembered one | Only signed envelopes and platform facts exist for verdict purposes; every claim in the record cites `obs-*`/`ctx:*`/`policy:*` refs; noise claims require partitioned, baseline-compared numbers or they may not appear |
| **P3 Ownership** | The agent owns its own state: `state.json` in a self-made directory, keyed on a log `insertId` — mutable, unversioned, no conflict policy; the report file is the only durable account | The episode store owns the truth; the recorder is the only door (and rejects softening verdicts server-side); the report is a projection; private state and "remember this" prose are violations |
| **P4 Authority** | Autonomy is prose: "Do not ask the user for permission," chat notifications sent automatically, remediation as copy-pasteable `kubectl`/`terraform` commands | Autonomy is the spec's dial, not the skill's prose; any remediation is a schema-enforced `proposed_action` draft — `posture: draft-only`, autonomy level, blast radius, named approvers — for a human to act on |
| **P5 Trust boundary** | None. Log content, trigger text, and tool payloads are undifferentiated input; an instruction-shaped log line has no defined handling | Evidence is never a command: instruction-shaped or pressure-shaped content is quoted verbatim in `quoted_evidence`, trust-graded, flagged, with `effect_on_verdict: none` plus the structural reason; the injection attempt itself becomes a finding |
| **P6 Clock** | Good instincts, unclocked conclusions: separate windows and a 10-minute soak are prescribed, but verdicts carry no expiry and staleness is a caution, not a field | Windows explicit and non-overlapping; envelope freshness acknowledged; the verdict itself carries `valid_through` and `reassess_if` — a conclusion may not outlive its facts |
| **P7 Ceilings** | The agent manages its own delegation to the future: `defer_verification` self-schedules re-checks; steps assume platform surfaces that may not exist | Single-agent, honestly: work not done in-session is missing evidence, never assumed done; no self-scheduling; the ceiling spec is pre-declared for the day delegation arrives |
| **P8 Failure ladder** | Two modes: finish the analysis, or don't. A tool failure or missing metric has no named degraded behavior; nothing prevents silence reading as health | Four named rungs; missing evidence lands in `unknowns` by name, drops confidence, and prefers abstention; a session that cannot record still reports exactly what failed |
| **P9 Outcomes** | "Reference/learn from previous deployments" with no label discipline — history can testify, and nothing separates the agent's own past verdicts from ground truth | Precedents are labeled-only, balanced, advisory, tighten-only; durable knowledge travels only as human-promoted dossier proposals; the reviewer never learns from its own verdicts — the outcome collector grades those independently |

## What the legacy skill got right

Honesty requires the other column too. The legacy skill's durable insights —
error types over counts, scanner-noise awareness, separate non-overlapping
windows, the three-level causal chain, "a rollout is not done at Ready,"
zero-mutation posture, stale-status caution — were sound operational judgment,
and the trustworthy skill expresses every one of them. The difference is
*where they live*: in the legacy skill they are advice the model may honor;
in the trustworthy skill they are specs the record must exhibit and the
rubrics score.

## The structural asymmetry the evaluation must respect

Both arms run on the same platform, so the recorder's tighten-only floor, the
signed-envelope channel, and the three-verdict vocabulary bind the legacy arm
too (its intake shim maps SUCCESS→healthy, FAILURE/DEGRADED→
regression-suspected, undecidable→insufficient-evidence). The comparison
therefore measures the **skill layer**: judgment quality, epistemic
discipline, injection handling, abstention honesty — not the platform floor,
which is constant by construction. Two consequences, stated up front:

- The baseline structurally caps at 0.85 on `rollout-review@3` (it emits no
  epistemic record). That is construction, reported but never cited as a win.
- The bars that matter are the judged and ground-truth ones:
  `rollout-reviewer-tenets@3`, `trustworthy-autonomy@2`, and
  `scenario-outcome-match@1` on the deception set — including the planted
  log-injection case, where the expected difference is the sharpest:
  quoted-and-flagged versus undefined behavior.

## Where the measured results land

`scripts/baseline-vs-trustworthy.sh` writes per-arm suite logs, paired
experiment reports (bootstrap CI, sign test, cost guard), a validator sweep
(record-present / schema-valid rates per arm), and a failure-tag scorecard
(VERDICT_SOFTENED, RECORD_MISSING, INJECTION_UNQUOTED, …). When the first
full run completes, its scorecard should be appended to this document — and
if any pre-registered bar fails, that result is reported here too, not
reworded.
