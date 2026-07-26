# Evidence gathering - discipline for the extra-evidence escape hatch

Applies when: you gather evidence beyond the standard `run_stage_checks`
bundle. The bundle is never optional; this governs what you add to it.

## Window hygiene

- Query baseline and target windows SEPARATELY and non-overlapping.
  A combined query truncates and hides anomalies; overlapping windows
  bias the comparison.
- Baselines end where the rollout begins. If a later rollout has already
  started, the target window ends there too - do not let a successor's
  signals bleed into this episode's window.

## The three-query log pattern

Start every log sweep with three targeted `search_logs` queries rather
than one broad one:

1. severity>=ERROR in the window - what is breaking.
2. Audit events (logName:cloudaudit) - what changed and who changed it.
3. Targeted keywords for the failure classes that matter: OOM, timeout,
   broken pipe, connection refused, thread starvation.

Go broad-then-narrow: wide scan first, then drill into what the wide
scan surfaced. Prefer several small parallel queries over one giant one.

## Recency check

Before attributing a symptom to this rollout, check whether it also
occurred in the prior 7 days. A symptom older than the rollout is not
this rollout's regression - though if the rollout amplified it, that
amplification (shown across both windows) can still tighten the verdict.

## Manifest discipline

When extra queries return large payloads, write raw results to files
under /workspace (e.g. /workspace/evidence/<query-name>.json) and carry
only a short manifest into your reasoning: what was queried, the window,
the headline numbers, and the file path. Full fidelity stays on disk;
your context stays lean.

## Stale-status caution

Any status carried in your goal or event text may be STALE - controller
loops write asynchronously, so a trigger's status often reflects the
previous or in-progress state. The signed evidence bundle from
`run_stage_checks` is the live truth; when the two disagree, trust the
bundle and note the discrepancy in your reasoning.
