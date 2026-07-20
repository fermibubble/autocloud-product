---
name: architecture-review-standards
version: 1.0.0
description: Governance review format for designs and IaC - risks with severity and blast radius, evidence items, assumptions, open questions, and approval-ready structure.
---
# Architecture review standards

Every design/IaC review you produce follows this structure (the org's
governance vocabulary):

- Summary: what is being built, in two sentences.
- Risks: each with severity (low/medium/high/critical), the blast radius
  if it materializes, and a concrete mitigation. Cost and reliability
  risks require a numeric estimate where possible.
- Evidence: each claim you make cites what you inspected (a resource, a
  metric, a config file) - reviews without evidence are opinions.
- Assumptions: everything you could not verify, stated explicitly.
- Open questions: what a human approver must decide; never bury a decision
  inside a recommendation.
- Verdict: approve / approve-with-conditions / revise, with the conditions
  enumerated.

Prefer boring, proven services over novel ones unless the requirement
demands otherwise; flag single points of failure, missing rollback paths,
unbounded cost surfaces, and any resource without an owner label.
