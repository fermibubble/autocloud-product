# rollout-reviewer

Staged post-deployment validation: one session per checkpoint of a rollout
episode (T+0/5/15/30 ladder driven by the relay), deterministic policy
enforcement, signed evidence, and a `healthy | regression-suspected |
insufficient-evidence` verdict. Read-only — no mutating verbs exist on
either MCP surface.

## Specs

| File | Registry name | Delta |
|---|---|---|
| `agentspec.yaml` | `rollout-reviewer` | live model (anthropic) |
| `agentspec.scripted.yaml` | `rollout-reviewer-scripted` | deterministic twin — **model section is the only diff** (provider: fake), so the pair stays experiment-comparable |

## Skills

- `rollout-validation-protocol@3.2.0` — the contract (checkpoint order,
  verdict vocabulary, trust rules) plus four on-demand playbooks:
  noise-isolation, scope-triage, evidence-gathering, stability-checks.
- `dossier-maintenance@1.0.0` — read/propose discipline for service
  dossiers.

## Evals

| Suite | Agent | Dataset | Rubric | Threshold |
|---|---|---|---|---|
| `golden` | rollout-reviewer-scripted | `rollout-golden` | `rollout-review@2` | 1.0 |
| `goals` | rollout-reviewer | `rollout-reviewer-goals` | `rollout-review@2` | 0.7 |

Dataset registry identity is the JSON `name` field, not the file path.
Keep non-dataset files in `evals/` as YAML/MD — any `.json` here is
published as a dataset by the bundle glob.

Run: `scripts/run-suite.sh rollout-reviewer [golden|goals]`
(needs harness up + `ENSEMBLE_TOKEN`; `goals` needs an ANTHROPIC_API_KEY
worker; `golden` needs sim + rollout-intel and the fake script below).

## Fake scripts

`fake-scripts/rollout-reviewer.json` drives the scripted twin — the
filename must equal the fake model id. Runtime workers discover it via
`FAKE_SCRIPTS_DIR`, an os.pathsep-joined list of roots:

```
FAKE_SCRIPTS_DIR=<repo>/autocloud-product/agents/rollout-reviewer/fake-scripts
```

Colon-join more roots (other agents' or products' script dirs) as needed.
