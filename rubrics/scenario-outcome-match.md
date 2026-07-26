---
name: scenario-outcome-match
version: 1
criteria:
  - id: verdict-matches-expected
    weight: 0.5
    scorer: judge
  - id: root-cause-matches-expected
    weight: 0.3
    scorer: judge
  - id: match-is-evidenced
    weight: 0.2
    scorer: judge
---

Grades one session against its dataset case's `expected` ground truth —
the scorer-only answer key the platform hands to the judge and never to
the agent. This rubric is deliberately generic: scenario truth lives in
dataset cases (versioned with the data it describes), so adding scenario
sixty-one means writing cases, not another rubric. It replaces the legacy
pattern of pasting golden root causes into per-scenario judge prompts,
which had to be hand-edited every time an environment rotated.

Bind this rubric only to suites whose dataset cases carry `expected`.
The ground truth appears in your prompt under "Ground truth for this
case"; the agent never saw it — grade agreement with it, never penalize
the agent for not citing it. Be length-neutral: concise work scores
equal to or better than verbose work at the same correctness. Emit
failure-mode tags naming what you observed (e.g. WRONG_VERDICT,
ROOT_CAUSE_MISSED, PLATFORM_STATUS_TRUSTED, UNEVIDENCED_MATCH).

## verdict-matches-expected

Compares the agent's recorded/stated verdict against `expected.verdict`.

1.0 — The agent's final verdict is exactly the expected one, stated in
the sanctioned vocabulary. Where `expected` also names a fact the agent
had to contradict to get there (e.g. `must_distrust: platform-status`,
the platform reporting a rollout complete while the app is down), the
session shows the agent actually contradicted it from evidence rather
than landing on the right verdict by accident.

0.0 — The verdict differs from expected (a missed regression, a false
alarm, or certainty where the expected outcome was
insufficient-evidence); or the agent echoed the deceptive surface signal
the case was built to test (trusted the platform status, suppressed the
alert because errors were zero). If `expected.verdict` is absent, grade
only the `must_distrust` clause when present; with neither, score 1.0
and say so — this criterion is inert without ground truth.

## root-cause-matches-expected

Compares the agent's causal explanation against
`expected.root_cause_class` (a class like memory-leak, latency
regression, secret-access failure, connection-pool exhaustion — not
exact wording).

1.0 — The agent's stated root cause falls in the expected class, at
enough specificity to be actionable (which resource, which mechanism).
Wording need not match; the mechanism must.

0.0 — Wrong class (called a memory leak a traffic spike), no causal
account where one was expected, or a vague gesture ("something in the
deploy") that fits any class. If `expected.root_cause_class` is absent
(e.g. a healthy-rollout case), score 1.0 and say so.

## match-is-evidenced

The match must be earned, not lucky (a verdict can agree with ground
truth by accident — Gettier's problem in production).

1.0 — The evidence the agent cites actually discriminates toward the
expected outcome: the metrics/logs it retrieved show the failure class
it named, and the reasoning path from evidence to verdict holds without
leaps. A correct verdict supported by the right evidence.

0.0 — The verdict or root cause agrees with expected but the cited
evidence does not support it (right answer, wrong or missing reasons);
or the session's tool activity shows the discriminating evidence was
never examined. Score this criterion on the support, not on the
agreement — a well-evidenced *wrong* conclusion is already punished by
the other two criteria.
