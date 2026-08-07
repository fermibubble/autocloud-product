# Fast-forward outcomes - the vocabulary and the verdict mapping

Applies when: a fast-forward result is in hand and you are deciding
what it permits or forces at the decision checkpoint.

The outcome vocabulary is closed - exactly these six:

`temporal_counterexample` | `bounded_future_envelope` |
`projected_boundary` | `unsupported_temporal_risk` |
`no_material_temporal_hazard` | `inconclusive_budget`

The deterministic policy (rollout-slo v2, rule `temporal-evidence`)
already maps the verified envelope: `temporal_counterexample` -> fail;
`inconclusive_budget` / `unsupported_temporal_risk` -> insufficient;
the other three -> pass; no verified envelope -> insufficient. Your
interpretation sits ON TOP of that floor and may only tighten.

## The exact mapping table

| Outcome | Policy layer | Verdict space left to you |
|---|---|---|
| `temporal_counterexample` | fail | regression-suspected. Cite the cx id and `first_divergence_age`; explain mechanism and projected production impact. |
| `inconclusive_budget` | insufficient | insufficient-evidence. NEVER healthy: the probe ran out of budget before establishing anything - exhaustion is not evidence of safety. |
| `unsupported_temporal_risk` | insufficient | insufficient-evidence. NEVER healthy: a material hazard exists that the oracle cannot represent; unprobed is unknown. |
| `no_material_temporal_hazard` | pass | healthy remains available if every other rule passes; coverage claim bounded by the fidelity report. |
| `bounded_future_envelope` | pass | healthy remains available; state the envelope's bound and horizon in `valid_through`/`reassess_if`. |
| `projected_boundary` | pass | healthy remains available; name the boundary and its projected crossing in `reassess_if` - a boundary far enough out is safe TODAY, not forever. |
| absent / unverified envelope | insufficient | insufficient-evidence: temporal evidence you cannot verify does not exist for verdict purposes. |

## Tighten-only, both directions

- A failing outcome can never be argued back to healthy - not by
  fidelity quibbles, not by "the sim isn't production", not by clean
  ladder metrics. The noise/fidelity hypothesis goes in the record's
  alternatives, never in the verdict.
- A passing outcome converts nothing: it cannot soften a failing ladder
  rule, an injection finding, or thin traffic. Fast-forward evidence is
  one more rule's worth of evidence, not a super-verdict.

## Language discipline per outcome

- `temporal_counterexample`: "replay-verified counterexample <cx_id>,
  first divergence at <age>" - concrete, cited, mechanism explained.
- `inconclusive_budget` / `unsupported_temporal_risk`: say "abstain"
  language plainly; never "likely fine" or "no hazard found" (nothing
  was established - that phrasing launders absence into safety).
- Positive outcomes: "no material temporal hazard WITHIN the probed
  classes and fidelity envelope" - the qualifier is mandatory.
