---
name: best-practices-review
version: 1
criteria:
  - id: report-written
    weight: 0.3
    scorer: programmatic
    check: { type: file_written, value: "design-review.md" }
  - id: risks-with-severity
    weight: 0.2
    scorer: programmatic
    check: { type: event_regex, value: "(?i)(severity|blast radius)" }
  - id: evidence-cited
    weight: 0.1
    scorer: programmatic
    check: { type: event_regex, value: "(?i)evidence" }
  - id: open-questions-surfaced
    weight: 0.1
    scorer: programmatic
    check: { type: event_regex, value: "(?i)(open question|assumption)" }
  - id: verdict-stated
    weight: 0.3
    scorer: programmatic
    check: { type: final_regex, value: "(?i)(approve(-with-conditions)?|revise)" }
---
## report-written
The governance review exists in the workspace.

## risks-with-severity
Risks are graded (severity / blast radius vocabulary appears in the report
or tool activity) - the org's control-plane review structure.

## evidence-cited
Claims cite inspected evidence; reviews without evidence are opinions.

## open-questions-surfaced
Unverifiable items are surfaced as assumptions/open questions instead of
being buried inside recommendations.

## verdict-stated
The final message states a verdict from the exact vocabulary:
approve / approve-with-conditions / revise.
