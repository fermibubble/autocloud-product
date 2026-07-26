# incident-manager

Parallel-hypothesis incident investigation via ceiling-clamped spawns;
blast-radius quantification; postmortem + comms drafts. Read-only
observation — mitigation is proposed, never executed.

## Specs

| File | Registry name | Delta |
|---|---|---|
| `agentspec.yaml` | `incident-manager` | autonomous read-only investigation |
| `agentspec.hitl.yaml` | `incident-manager-hitl` | human-in-the-loop dial — **permission section is the only diff** (`unlistedMcpTools: ask`), every cloud call waits for approval |

## Skills

- `incident-playbook@1.1.0` — the five playbook rules and the
  confidence gate, plus three on-demand playbooks:
  parallel-investigation (spawn briefings, non-overlapping domain
  plans), outage-correlation (impact verdict discipline, platform-event
  dedup), exec-report-card (optional third deliverable
  `/workspace/exec-report-card.md`).

## Evals

| Suite | Agent | Dataset | Rubric | Threshold |
|---|---|---|---|---|
| `goals` | incident-manager | `incident-manager-goals` | `incident-review@1` | 0.7 |

The hitl variant is intentionally not a default suite — `ask`-gated calls
stall unattended eval runs; an attended suite is stubbed (commented out)
in `evals/suite.yaml`.

Dataset registry identity is the JSON `name` field, not the file path.
Keep non-dataset files in `evals/` as YAML/MD — any `.json` here is
published as a dataset by the bundle glob.

Run: `scripts/run-suite.sh incident-manager`
(needs harness up + `ENSEMBLE_TOKEN` + an ANTHROPIC_API_KEY worker).
