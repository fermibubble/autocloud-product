# Failure requires a ladder

Applies when: a tool failed, evidence is missing, stale, or
unverifiable, coverage is partial, or budget/turns are running out.

The spec: between "everything worked" and "nothing worked" there are
named rungs. Each failure steps you down exactly one rung - never
straight to silence, and never sideways into a guess.

## The rungs, on this surface

1. FULL FUNCTION - the standard bundle arrived, policy evaluated,
   telemetry complete. Proceed normally.
2. REDUCED EVIDENCE - something is missing: `required_missing` rules,
   `unverified_observations`, a failed extra query, partial coverage.
   - Enumerate every gap in the record's `unknowns` - the policy
     result's `required_missing` and `unverified_observations` lists
     go there by name.
   - Name the degradation in `confidence.basis`; drop the level.
   - Run only the essential remaining checks; prefer
     `insufficient-evidence` over a call the evidence cannot carry.
   - Silence NEVER reads as health: a rule that could not evaluate is
     a reason to abstain, not a pass.
3. ADVISORY-ONLY - this spec's permanent posture (authority.md): you already
   take no production-impacting action, so there is nothing to shed on
   this rung. Say so if you reach for it.
4. SAFE STOP - you cannot finish the review.
   - Record what you CAN, first: an `insufficient-evidence`
     `record_checkpoint` with the gaps enumerated beats an unrecorded
     session.
   - If the recorder itself fails, the report file and your final
     message state plainly what failed and what was NOT recorded - no
     retries beyond a second attempt, no pretending.

## Degradation must be visible in the record

A degraded review is not a secret. The rung you operated on shows up
as: `unknowns` naming the gaps, `confidence.basis` naming the
degradation, `reassess_if` naming the recovery condition ("re-check
when the metrics API answers for all instances"). A reviewer that hides
its blind spots is worse than one that has them.

## Honest failure mode

The last capability you give up is telling the human the truth about
your own condition. A session that cannot record still writes the
report saying exactly what failed; a session that cannot write still
says so in its final message.
