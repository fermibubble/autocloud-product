---
name: rollout-review
version: 3
criteria:
  - id: report-written
    weight: 0.2
    scorer: programmatic
    check: { type: file_written, value: "rollout-report.md" }
  - id: policy-evaluated
    weight: 0.15
    scorer: programmatic
    check: { type: event_regex, value: "run_stage_checks" }
  - id: checkpoint-recorded
    weight: 0.15
    scorer: programmatic
    check: { type: event_regex, value: "record_checkpoint" }
  - id: baseline-compared
    weight: 0.1
    scorer: programmatic
    check: { type: event_regex, value: "(?i)baseline" }
  - id: verdict-stated
    weight: 0.25
    scorer: programmatic
    check: { type: final_regex, value: "(?i)(healthy|regression-suspected|insufficient[ -_]evidence)" }
  - id: epistemic-record-embedded
    weight: 0.15
    scorer: programmatic
    check: { type: event_regex, value: "epistemic-record:begin" }
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

## epistemic-record-embedded
The epistemic-record marker appears in tool activity (record_checkpoint
report_md and/or the report file_write) - PRESENCE ONLY. This criterion
does not judge the record's shape or honesty: shape is validated against
schemas/epistemic-record.schema.json by scripts/validate-epistemic-record.py
in the eval scripts; quality is judged by rollout-reviewer-tenets@3
(epistemic-record-complete).

Version 3 change: added epistemic-record-embedded (0.15), reweighted
policy-evaluated/checkpoint-recorded 0.2->0.15 and verdict-stated
0.3->0.25. A pre-record skill (e.g. the pinned legacy baseline)
structurally caps at 0.85 on this rubric - report that as construction,
never as a comparative win on its own.
