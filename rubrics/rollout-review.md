---
name: rollout-review
version: 1
criteria:
  - id: report-written
    weight: 0.4
    scorer: programmatic
    check: { type: file_written, value: "rollout-report.md" }
  - id: baseline-compared
    weight: 0.3
    scorer: programmatic
    check: { type: event_regex, value: "(?i)baseline" }
  - id: verdict-stated
    weight: 0.3
    scorer: programmatic
    check: { type: final_regex, value: "(?i)(healthy|regression)" }
---
## report-written
The staged rollout report was produced in the workspace.

## baseline-compared
Tool activity shows metrics were actually compared against the 24-hour
baseline, not just described.

## verdict-stated
The final message states the overall verdict plainly.
