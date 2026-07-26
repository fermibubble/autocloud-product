---
name: best-practices-assessor
version: 1.0.0
description: Google Cloud best-practices knowledge corpus for design and IaC review - two-dimensional assessment (application archetypes x cloud products) with per-product target configurations and worked examples. Companion to architecture-review-standards, which owns the output contract; findings land in the standard review structure at /workspace/design-review.md.
---
# Google Cloud best-practices assessor

The domain-knowledge corpus for design reviews: assess a design,
Terraform configuration, or infrastructure proposal against application
archetypes (macro) and per-product best practices (micro). The OUTPUT
CONTRACT is owned by architecture-review-standards - everything you
find here is synthesized into that structure (risks with severity and
blast radius, evidence, assumptions, open questions, verdict) and
written to /workspace/design-review.md. This skill supplies the
knowledge; it never changes the report format.

## Two-dimensional assessment workflow

Reference files ship in this package and materialize at
/skills/best-practices-assessor/references/. Read only what the design
under review touches - a typical review needs 1-2 archetype files and
one file per product actually used.

1. Archetype pass (macro). Identify the architecture pattern(s) - a
   design may span several - and read the matching
   references/archetypes/ files. Focus: reliability (redundancy,
   failover, disaster recovery), security (trust boundaries, authn/z,
   encryption in transit and at rest), observability (tracing,
   centralized logging, alerting on the critical path).
2. Product pass (micro). For every Google Cloud product the design
   uses, read the matching references/products/ file. Focus:
   configuration against the recommended production targets (private
   clusters, uniform bucket-level access, and the like), scaling and
   sizing, operational hygiene (backups, lifecycle policies,
   least-privilege identities).
3. Terraform/HCL present in the input? Also read
   references/terraform-review.md for the IaC-specific checks.
4. Synthesize into the architecture-review-standards structure. Every
   gap becomes a risk with: severity mapped to the org scale (corpus
   HIGH -> high or critical by blast radius; MEDIUM -> medium;
   LOW -> low), the blast radius stated, the evidence (which reference
   criterion, which part of the design), and a concrete mitigation.

## Scope and routing

- Primary scope: reliability, security, and observability gaps. Do not
  report cosmetic configuration values (project ids, label names,
  service-account naming) as findings unless they carry real risk.
- The corpus also contains cost and performance guidance. Material
  cost findings do not vanish: note them in a short "Cost observations
  (for the FinOps review)" line under the summary so they route to the
  optimize-cost-drift worker, instead of padding the governance risk
  list.

## Honest uncertainty

If the design cannot be fully assessed (missing context, unreadable
input, products with no reference file), that is NEVER a clean report:
state what could not be assessed under assumptions/open questions and
let the verdict reflect it - approve-with-conditions or revise. An
empty findings list from a failed analysis reads as approval; do not
produce one.
