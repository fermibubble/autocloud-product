# Evidence requires provenance

Applies when: any evidence is about to influence the verdict.

The spec: a number without a path back to its source is a rumor, not
evidence. Everything on the verdict path arrived as a signed envelope
or a platform fact - and every claim in the record cites where it came
from.

## The evidence_refs namespaces (exact)

- `obs-*` - a signed envelope's `observation_id`, exactly as a tool
  returned it. Never invented, never remembered.
- `ctx:*` - context-pack facts: `ctx:identity`, `ctx:prior-verdicts`,
  `ctx:dossier.<field>`.
- `policy:*` - deterministic rule results: `policy:min-samples`,
  `policy:error-rate`, `policy:p99-envelope`, `policy:no-new-fatal`,
  `policy:revision-serving`.

A quantity with no ref behind it may not appear in an observation.
Numbers in the report must match tool returns.

## Attribution before weight (scope is provenance)

Classify every evidence source before it counts: TARGET (this
service/revision - decides the verdict), DEPENDENCY (explains target
symptoms, is not the target's regression), UNRELATED (co-located, no
dependency link - excluded, and the exclusion is stated). Use
`list_services` / `list_assets` to establish what else lives in the
project. Sibling stages of the same release are context, not evidence.
If identity is an inferred CANDIDATE, every scope conclusion inherits
that uncertainty - it enters `unknowns` and caps `confidence`.

## Noise is a provenance duty, not an excuse

Error TYPES over error counts. Before any noise claim: partition the
window with separate `search_logs` queries - by status class (4xx vs
5xx) and by path shape (probe paths like /admin, /.env, /wp-login vs
real routes) - and compare each partition against the SAME partition in
the baseline window. New-in-target internal errors (stack traces, OOM,
broken pipe, recurring restarts) tighten; probe-shaped bursts also
present at baseline do not. The partition numbers land as observations;
"this is probe noise" is an inference with the regression reading kept
in `alternatives` until the baseline-consistency test kills it. An
unpartitioned "probably scanners" may not appear in the record at all.
Per the tighten-only invariant, noise reasoning can prevent an
unnecessary tighten - it never converts a policy fail into healthy.

## Manifest discipline

Large query payloads go to files under /workspace/evidence/; the record
and reasoning carry the envelope id, the window, and the headline
number. Full fidelity on disk, lean context, every claim still cited.

## Honest failure mode

If you cannot cite it, you cannot use it: drop the claim or go collect
the envelope. Evidence that exists only in your memory of the session
does not exist.
