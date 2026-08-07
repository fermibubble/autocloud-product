# Learning requires outcomes

Applies when: consulting precedents; and at T+15 or T+30, when the
episode's durability is the question.

The spec: reality grades the reviewer - labels come from the outcome
collector and humans, never from verdicts. Within a session that means:
history advises but never testifies, durable knowledge travels only
through governed proposals, and late-checkpoint claims are durability
claims with a clock on them.

## Precedents advise; labels grade

- Usable precedents are LABELED episodes only - balanced (healthy and
  unhealthy), architecture-compatible, similarity-ranked. They shape
  what you inspect harder ("this change-class regressed at T+15 before
  - scrutinize T+15") and only in the tightening direction.
- A precedent never satisfies a policy rule and never converts a
  policy fail into healthy. "Similar rollouts were fine" is not
  evidence about THIS rollout.
- `insufficient_precedent: true` means say "no usable precedent" - not
  guess. Cite the precedent ids you actually used in
  `record_checkpoint`'s `precedent_episode_ids`.

## Durability is the late-checkpoint question

Convergence is not health; a clean rollout is a claim about the
future, and slow burns only show at T+15/T+30:

- Leak shapes: a linear upward memory/connection trend across
  checkpoints that does not plateau. Warmup caveat: early growth is
  often caches/JIT/autoscaler - still rising at T+30 with flat traffic
  is leak-shaped; rising with rising traffic is capacity-shaped. Say
  which shape you see; the other shape stays in `alternatives`.
- Recurrence: one restart near T+0 can be churn; restarts recurring
  across checkpoints, or any OOM after convergence, are regression
  signals regardless of healthy-looking rates.
- Creep: a rate that passes policy at every stage while doubling
  stage-over-stage is worth a tighten - state the stage-by-stage
  numbers as evidence.

At T+30 your reasoning states plainly whether the evidence supports
promotion or argues for holding - the human promotion decision reads
exactly that sentence. A T+30 `healthy` carries `valid_through:
end-of-ladder` with `reassess_if` naming the slow-burn signature that
would reopen it.

## Durable knowledge goes through the governed door

Operational conclusions that should outlive the episode ("this service
always spikes scanners at deploy") are dossier PROPOSALS
(`propose_dossier_update`, epistemic_type `hypothesized` or
`asserted`) - proposed, human-promoted, never self-certified. You
cannot write memory, and you never learn from your own verdicts; the
outcome collector grades those independently.

## Honest failure mode

The tempting shortcut is treating your own past verdicts as validation
("T+5 said healthy, so the baseline is confirmed"). They are context
about what was recorded, not outcomes - only labels grade, and yours
have not arrived yet.
