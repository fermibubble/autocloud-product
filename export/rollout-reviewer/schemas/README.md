# Schemas — one spec per principle, one composition root

Each trustworthy-autonomy principle that produces a machine-checkable
artifact has its own schema file in this directory, independently
loadable so a harness can adopt principles incrementally. The epistemic
record
(`epistemic-record.schema.json`) is the composition root: it IS the P1
spec and pulls the sub-specs in by `$ref`. Validating a report against
the root validates every referenced principle at once — the record is
recorded atomically, so it is validated atomically; the decomposition
changes reuse, not semantics.

| Principle | Schema | Validates |
|---|---|---|
| P1 Epistemics | `epistemic-record.schema.json` (root) | The whole record: observations, inferences, confidence, unknowns, discriminating checks — plus everything below via `$ref` |
| P2 Provenance | `evidence-ref.schema.json` | A single evidence citation (`obs-*` \| `ctx:*` \| `policy:*`) |
| P2 Provenance | `evidence-envelope.schema.json` | A signed observation envelope — standalone; validate your own tool outputs against it if you bridge/reimplement the observe surface |
| P4 Authority | `proposed-action.schema.json` | A draft-only remediation (posture is `const: draft-only` — an executed action is unrepresentable) |
| P5 Trust boundary | `quoted-evidence.schema.json` | One quarantined suspicious payload (verbatim content, trust grade, flags, `effect_on_verdict: none …`) |
| P6 Clock | `validity-horizon.schema.json` | `$defs` for `valid_through` / `reassess_if` — the verdict's own expiry |
| P9 Outcomes | `outcome.schema.json` | The ground-truth label body your collector POSTs to `/intel/episodes/{id}/outcome` — standalone |

**Principles with no schema, on purpose** — they are properties of the
system, not shapes of a document:

| Principle | Where it is enforced instead |
|---|---|
| P3 Ownership | The recorder (see TOOL-CONTRACT.md `record_checkpoint`): single write door, server-side policy re-run, `policy_conflict` rejection, replay-safe completion, decision audit rows |
| P7 Ceilings | Agent posture (AGENT-CONTRACT.md §3): single-agent protocol; work not done in-session is missing evidence — a session property no document schema can attest |
| P8 Failure ladder | Behavior under degradation, made *visible through* P1 fields (`unknowns` naming gaps, `confidence.basis` naming the degradation) and scored in evals — not a separate artifact |

Validation tooling: `scripts/validate-epistemic-record.py` resolves the
`$ref`s automatically (a file-based registry rooted at this directory);
`--self-test` keeps the schemas and the skill's worked examples from
drifting apart. Full payload examples: `examples/report.md` (record),
`examples/trace.jsonl` (envelopes), AGENT-CONTRACT.md §4 (outcome).

## Enforcement model — where these schemas are enforced (and where not)

**The recorder deliberately never gates on schema validity.** This is a
design decision, not an omission: the recorder fails closed on
*decisions* (verdict vocabulary, tighten-only floor, policy
consistency, scope) and fails open on *documentation format*. A verdict
must never be lost to a yaml mistake — a schema-invalid-but-honest
record that is stored is recoverable and attributable; an unrecorded
verdict is neither. Gating storage on format would also put the agent
in a rejection loop with the store over syntax while the checkpoint
sits unrecorded. Do not "fix" this by adding jsonschema to
rollout-intel.

The schema is instead enforced at three points, all sharing this one
definition:

1. **In-session self-check (the primary point):** after a successful
   `record_checkpoint`, the session runs the validator against its own
   episode and, on a nonzero exit, fixes the record and re-records once
   (recording is replay-safe). Format convergence happens while the
   agent's context is still alive to fix it.
2. **Your eval loop:** `--episode` after sessions; typed exit codes
   (2/3/4/5/6) classify failures.
3. **The scorer:** `rr validate` as the deterministic pre-score; the
   epistemics rubric grades the record's honesty on top.

Consumption is gated even though storage is not: promotion decisions,
dossier proposals, and comparison scorecards act only on records that
validate (exit 0). Store everything; act on what validates.
