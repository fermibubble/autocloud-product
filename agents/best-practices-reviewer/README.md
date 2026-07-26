# best-practices-reviewer

Design & IaC review against the governance skill corpus — best practices
ARE versioned skills (`architecture-review-standards`), so policy updates
are skill publishes, not prompt edits. Delivers `/workspace/design-review.md`
in the standard structure: risks with severity and blast radius, evidence,
assumptions, open questions, verdict
(`approve | approve-with-conditions | revise`).

## Specs

| File | Registry name | Delta |
|---|---|---|
| `agentspec.yaml` | `best-practices-reviewer` | live model, read-only autonomy |

(Renamed from `design-governance`; the old name remains frozen in the
registry — `ensemble apply` never deletes.)

## Skills

- `architecture-review-standards@1.0.0` — owns the review output
  contract (risks/severity/blast radius, evidence, assumptions, open
  questions, verdict) that the rubric scores.
- `best-practices-assessor@1.0.0` — the domain-knowledge corpus:
  37 archetype × product reference files plus terraform-review checks,
  synthesized into the standards structure at
  `/workspace/design-review.md`.

## Evals

| Suite | Agent | Dataset | Rubric | Threshold |
|---|---|---|---|---|
| `goals` | best-practices-reviewer | `best-practices-reviewer-goals` | `best-practices-review@1` | 0.7 |

Dataset registry identity is the JSON `name` field, not the file path.
Keep non-dataset files in `evals/` as YAML/MD — any `.json` here is
published as a dataset by the bundle glob.

Run: `scripts/run-suite.sh best-practices-reviewer`
(needs harness up + `ENSEMBLE_TOKEN` + an ANTHROPIC_API_KEY worker).
