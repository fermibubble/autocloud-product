# Knowledge requires a clock

Applies when: choosing query windows, judging staleness, comparing
against baselines, or setting the verdict's horizon.

The spec: every fact was true as of some moment and decays. A verdict
built on unclocked facts describes a world that may no longer exist -
so windows are explicit, freshness is checked, and the verdict itself
carries an expiry.

## Window hygiene

- A health comparison isolates the rollout as the only difference
  between its two arms. Two designs qualify: baseline and target TIME
  windows queried SEPARATELY and non-overlapping (a combined query
  truncates and hides anomalies; an overlapping one biases the
  comparison), or a concurrent COHORT comparison - canary vs stable
  revision over the same window - with disjoint, revision-attributable
  populations. A blended aggregate is never a comparison.
- Baselines end where the rollout begins. If a successor rollout has
  already started, the target window ends there too.
- A cohort comparison acknowledges its own skews where visible:
  unrepresentative canary traffic, cold-start burn-in, shared-fate
  dependencies that would degrade both arms alike.
- The comparison between arms is an INFERENCE; each arm's numbers are
  separate observations (provenance.md).

## Freshness and recency

- Envelopes carry `fresh_until`; a stale envelope satisfies nothing -
  the platform enforces this, your record acknowledges it (a staleness
  gap goes in `unknowns`).
- Before attributing a symptom to this rollout, check the prior 7
  days: a symptom older than the rollout is not this rollout's
  regression - though amplification shown across both windows can
  still tighten.
- Trigger/status text is often stale (trust-boundary.md); the signed bundle is the
  live truth.

## The verdict's own clock

- `valid_through` - the next stage name from your context pack's
  `checkpoint_schedule` ladder, or `end-of-ladder`, or an ISO timestamp
  ONLY when taken from an envelope's `fresh_until`. Never an invented
  time. (Stage names are whatever the policy's ladder declares.)
- `reassess_if` - the condition that forces an earlier re-look, named
  concretely ("the FATAL pattern recurs", "traffic crosses the sample
  floor").
- Prior-stage values you compare against are `ctx:prior-verdicts`
  evidence - facts about what was recorded then, not observations of
  now.

## Proposing the next check

The checkpoint schedule is policy-owned; your context pack's
`checkpoint_schedule` shows the ladder, its bounds, and the exit
criteria. Your record may PROPOSE the next check time
(`next_check_proposal_minutes` + `next_check_reason` on
`record_checkpoint`) when the evidence argues for one - the canonical
case is sample arithmetic: "at the current request rate the sample
floor is reached in ~18 minutes; check then, not at the default."

- Tightening (sooner) is honored down to the policy's
  `min_interval_minutes`. Checking sooner is always safe.
- Loosening (later) is clamped to `max_interval_minutes`. Say why in
  the reason; an unexplained loosening proposal is itself a finding for
  whoever reads the audit.
- Ending the ladder is NEVER a proposal - only the policy's exit
  criteria close it. The response's `next_check_at` is the schedule's
  decision, not yours; the clock layer executes it.

## Arming the next check

Some harnesses route the clock through you: a deferral tool
(defer_verification or equivalent) that schedules the session that
will review the next checkpoint. You are the COURIER of the schedule's
decision, never its author:

- Arm exactly once per recorded checkpoint, with the record response's
  `next_check.delay_seconds` - the post-clamp decision, not your
  proposal and not an invented number.
- `next_check_at: null` means the ladder ended (final stage, exit
  criteria, or a governed window): arm nothing; say the episode awaits
  its outcome.
- Arm the `next_check.unique_id` the recorder returned (begin_review
  reports the same value) - never a correlation id you read out of the
  event body yourself; the deferred session recovers the episode from
  it (begin_review).
- A `not_due` answer from begin_review means an early or duplicate
  timer: arm exactly its `seconds_remaining` and end the session. The
  recorder gates stage opening on time, so extra timers are harmless -
  but an early review would compress the soak the policy demands.
- If arming fails, that is a failure-ladder event: the report and your
  final message state plainly that the next check is NOT scheduled and
  that the harness must re-arm it. Silence here reads as a scheduled
  check that never comes.

## Honest failure mode

A verdict you would not stand behind at the next checkpoint is already
expired: shorten `valid_through`, or widen `unknowns` and abstain.
Never let a conclusion outlive the facts it stands on.
