---
name: finops-review
version: 1.0.0
description: Cost-optimization review - idle and over-provisioned resource detection via Recommender, anomaly-to-deploy correlation, and the savings-report format with draft remediation.
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
