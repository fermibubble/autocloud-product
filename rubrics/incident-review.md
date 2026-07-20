---
name: incident-review
version: 1
criteria:
  - id: report-written
    weight: 0.4
    scorer: programmatic
    check: { type: file_written, value: "incident-report.md" }
  - id: comms-drafted
    weight: 0.3
    scorer: programmatic
    check: { type: file_written, value: "comms.md" }
  - id: root-cause-stated
    weight: 0.3
    scorer: programmatic
    check: { type: final_regex, value: "(?i)(root cause|hypothes)" }
---
## report-written
The postmortem exists with timeline and blast radius.

## comms-drafted
Stakeholder notification drafts exist.

## root-cause-stated
The final message names a root cause or the surviving hypothesis.
