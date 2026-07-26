# optimize-cost-drift

FinOps cost & drift sweeps via the GCP Recommender API: idle and
over-provisioned resources, anomaly correlation against deploys, findings
ranked by monthly savings with a draft Terraform/gcloud remediation per
finding. Drafts are proposals for human review — nothing is executed.

## Specs

| File | Registry name | Delta |
|---|---|---|
| `agentspec.yaml` | `optimize-cost-drift` | live model, read-only autonomy |

(Renamed from `optimize-agent`; the old name remains frozen in the
registry — `ensemble apply` never deletes.)

## Skills

- `finops-review@1.1.0` — the sweep contract plus two on-demand
  playbooks: gce-modernization (generation/storage upgrade advisory
  with named human-input assumptions) and stuck-savings (scale-down
  blocker taxonomy with `search_logs` evidence queries).

## Evals

| Suite | Agent | Dataset | Rubric | Threshold |
|---|---|---|---|---|
| `goals` | optimize-cost-drift | `optimize-cost-drift-goals` | `cost-drift-review@1` | 0.7 |

Dataset registry identity is the JSON `name` field, not the file path.
Keep non-dataset files in `evals/` as YAML/MD — any `.json` here is
published as a dataset by the bundle glob.

Run: `scripts/run-suite.sh optimize-cost-drift`
(needs harness up + `ENSEMBLE_TOKEN` + an ANTHROPIC_API_KEY worker).
