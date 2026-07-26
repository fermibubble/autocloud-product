---
name: finops-review
version: 1.1.0
description: Cost-optimization review - idle and over-provisioned resource detection via Recommender, anomaly-to-deploy correlation, and the savings-report format with draft remediation - with on-demand playbooks for GCE generation/storage modernization and diagnosing stuck savings.
---
# FinOps review

1. Pull idle-resource and rightsizing recommendations; translate each into
   monthly savings with the resource named.
2. Correlate any cost anomaly with recent deploys or traffic changes
   before blaming waste - a spike with a cause is not waste.
3. Deliverable: /workspace/finops-report.md - findings ranked by savings,
   each with: resource, evidence, monthly estimate, risk of acting, and a
   draft remediation (Terraform or gcloud) presented as a proposal.
4. Never execute remediations; drafts are for human review. State this in
   the report.

## Review playbooks (read on demand)

Detailed playbooks ship in this package at
/skills/finops-review/references/. Read the ones that apply to this
sweep; skip the rest:

- Findings involve older-generation compute (N1/N2) or legacy
  Persistent Disk -> references/gce-modernization.md (generation and
  storage upgrade advisory: rightsizing discipline, Hyperdisk sizing,
  TCO framing).
- A previously reported recommendation is still unrealized - the idle
  or oversized resource persists sweep over sweep ->
  references/stuck-savings.md (why scale-down is blocked, with the
  evidence queries).
