# Stability checks - late-checkpoint durability analysis

Applies when: STAGE is T+15 or T+30. Convergence is not health - a clean
rollout is a durability claim, and slow-burning regressions (leaks, pool
exhaustion, error creep) only become visible at the later checkpoints.

## Leak suspicion

- A linear upward trend in memory or connection usage across the
  episode's checkpoints is the leak signature. Compare this stage's
  utilization against the T+0/T+5 values recorded in prior checkpoint
  verdicts and reports.
- Warmup caveat: early linear growth is often benign - caches filling,
  JIT compilation, autoscaler ramp. The question is whether the trend
  PLATEAUS. Still rising at T+30 with flat traffic is leak-shaped;
  rising alongside rising traffic is capacity-shaped. Say which shape
  you see.

## Restart and crash recurrence

A single restart near T+0 can be scheduling churn. Restarts that RECUR
across checkpoints - or any out-of-memory kill after convergence - are
regression signals regardless of otherwise healthy-looking rates.

## Slow-burn creep

Compare error rate and latency drift ACROSS stages, not only against
the threshold: a rate that passes policy at every stage while doubling
stage-over-stage is creep worth a tighten - state the stage-by-stage
numbers as your evidence.

## Promote/hold reasoning at T+30

T+30 closes the ladder. Your `record_checkpoint` reasoning should state
plainly whether the episode's evidence supports promotion or argues for
holding, and why - the human promotion decision reads exactly this
sentence. Durable operational conclusions that should outlive the
episode (e.g. "this service always spikes scanners at deploy") belong in
a dossier proposal (`propose_dossier_update`, per dossier-maintenance) -
proposed, never asserted as governed truth.
