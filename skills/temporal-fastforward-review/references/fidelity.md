# Fidelity - how far the oracle's evidence reaches

Applies when: any positive fast-forward outcome is about to support a
healthy verdict; or a coverage claim is about to enter the report.

A fast-forward run happens against a probe instance driven by a
behavior spec, not against production. The fidelity report inside the
result packet is the oracle's own honesty about that gap - and it is
the OUTER BOUND of any claim you may make. You can narrow its language;
you can never widen it.

## The fidelity report

- `axes` - named dimensions each scored for how faithfully the probe
  reproduced the candidate's real conditions (workload shape,
  dependency behavior, time compression, state representativeness).
  Read them individually; an aggregate hides the weak axis.
- `aggregate` - the combined score. Useful for trend, never for
  coverage claims: claims cite axes.
- `gates_met` - whether the HARD GATES passed. A positive outcome with
  gates unmet is not positive evidence; treat it as if the result were
  absent and say why. Gates are the floor below which the oracle's
  evidence does not count.
- `unsupported` - hazard classes or conditions the run could not
  represent. This list transcribes DIRECTLY into your epistemic
  record's unknowns. Silence about an unsupported axis is a coverage
  lie by omission.

## The sim state-representativeness cap

The probe replays a state slice, not production state: production
connection reuse, cache warmth, tenant mix, and data shape are
approximated. State representativeness is therefore structurally
CAPPED - no fast-forward run, however clean, certifies behavior on
state shapes the slice does not contain. Consequences:

- A `no_material_temporal_hazard` outcome supports "no hazard within
  the probed classes and the replayed state slice" - never "no hazard".
- A counterexample survives the cap asymmetrically: a failure the probe
  CAN produce is real (the mechanism exists in the candidate); a
  failure the probe cannot produce proves nothing about absence. Caps
  weaken green evidence, not red.

## Honest-coverage language

Sanctioned phrasing for reports and records:

- "No material temporal hazard found within the probed hazard classes
  (<list>) and the fidelity envelope; unsupported: <list or none>."
- "Bounded future envelope: <metric> projected to stay within <bound>
  through <horizon> under replayed conditions."
- "Projected boundary at <age/condition>; not reached within <horizon>;
  reassess if production ages faster than the projection."

Forbidden phrasing: "temporally safe", "no future risk", "verified for
production", or any coverage sentence that does not survive placing
"...within the fidelity envelope" at its end.

## Failure mode to avoid

Fidelity is not a discount you apply to bad news. The tempting misuse
is "the counterexample is sim-only, production will differ" - that is
the softening move, and it is forbidden: the mechanism is in the
candidate's code; only its TIMING varies with fidelity. Put timing
uncertainty in the record; leave the verdict tightened.
