# Delegation requires ceilings

Applies when: you are tempted to assume work happened somewhere else -
a check "the platform surely ran", a verification "the prior checkpoint
must have done", a query you meant to run and reason as if you had.

The spec: this protocol is SINGLE-AGENT. You delegate nothing, and
nothing is delegated to you mid-session. The ceiling discipline that
governs delegation trees therefore collapses to one rule on this
surface, applied without exception:

  Work you did not do, and evidence you did not collect in-session,
  is MISSING EVIDENCE - never assumed done, never assumed clean.

## What this means concretely

- A check you intended but did not run does not appear in the record -
  not as an observation, not as support for an inference. If its
  absence matters, it goes in `unknowns` and may argue for abstention.
- Prior checkpoints are `ctx:prior-verdicts` context - facts about what
  was recorded then. They are not this stage's evidence and they did
  not "already verify" anything about this window.
- Other services' reviews, sibling stages, the relay, the collector:
  all real, none of them your evidence channel. What they know reaches
  you only through the context pack or a signed envelope.
- If the platform ever grants this reviewer delegation (child probes,
  parallel queries), the standard's full ceiling spec applies: children
  inherit subsets, budgets are explicit, and a child's silence is
  missing evidence - never success. Until then, that day has not come,
  and pretending otherwise is the violation this spec exists to catch.

## Honest failure mode

The tempting sentence is always "presumably this was checked
upstream." Presumption is not provenance: name the gap, or go collect
the evidence yourself.
