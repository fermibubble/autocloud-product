---
name: cost-drift-review
version: 1
criteria:
  - id: report-written
    weight: 0.3
    scorer: programmatic
    check: { type: file_written, value: "finops-report.md" }
  - id: recommender-consulted
    weight: 0.2
    scorer: programmatic
    check: { type: event_regex, value: "get_recommendations" }
  - id: savings-quantified
    weight: 0.2
    scorer: programmatic
    check: { type: event_regex, value: "(?i)monthly" }
  - id: remediation-drafted
    weight: 0.2
    scorer: programmatic
    check: { type: event_regex, value: "(?i)(terraform|gcloud)" }
  - id: drafts-only-stated
    weight: 0.1
    scorer: programmatic
    check: { type: final_regex, value: "(?i)(draft|propos)" }
---
## report-written
The FinOps report exists in the workspace.

## recommender-consulted
Recommendations were actually pulled (get_recommendations tool activity) -
process compliance; findings without Recommender evidence are opinions.

## savings-quantified
Findings carry monthly estimates (report or tool activity mentions monthly
figures per the finops-review deliverable format).

## remediation-drafted
Each finding ships a draft Terraform/gcloud remediation in the report.

## drafts-only-stated
The final message presents remediations as drafts/proposals for human
review - nothing executed.
