---
name: rollout-review
version: 2
criteria:
  - id: report-written
    weight: 0.2
    scorer: programmatic
    check: { type: file_written, value: "rollout-report.md" }
  - id: policy-evaluated
    weight: 0.2
    scorer: programmatic
    check: { type: event_regex, value: "run_stage_checks" }
  - id: checkpoint-recorded
    weight: 0.2
    scorer: programmatic
    check: { type: event_regex, value: "record_checkpoint" }
  - id: baseline-compared
    weight: 0.1
    scorer: programmatic
    check: { type: event_regex, value: "(?i)baseline" }
  - id: verdict-stated
    weight: 0.3
    scorer: programmatic
    check: { type: final_regex, value: "(?i)(healthy|regression-suspected|insufficient[ -_]evidence)" }
---
## report-written
The stage report exists in the workspace.

## policy-evaluated
The deterministic policy actually ran (run_stage_checks tool activity) -
process compliance, not verdict correctness; correctness is asserted
against rollout-intel ground truth by the golden scripts.

## checkpoint-recorded
The verdict was durably recorded into the episode.

## baseline-compared
Tool or report activity shows baseline comparison happened.

## verdict-stated
The final message states a verdict from the exact vocabulary, including
insufficient-evidence as a first-class outcome.
