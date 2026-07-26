# Terraform review checks - IaC-specific criteria

Applies when: the input under review contains Terraform/HCL. These are
REVIEW criteria - you flag, the author fixes; you never rewrite their
code.

## Structure

- Module preference: prefer approved/registry modules over raw
  resource blocks where a suitable module exists - flag hand-rolled
  resources that a maintained module already covers. BUT match the
  input's style: if the author works resource-first throughout, review
  their resources on their merits rather than demanding a module
  rewrite.
- Inter-module wiring: connection strings, network identifiers
  (subnets, VPC names), keys and endpoints should flow through module
  output bindings, not hand-typed string literals. A hardcoded value
  that duplicates another module's output is drift waiting to happen -
  flag it (pre-existing shared defaults are the exception when clearly
  intentional).

## Supply chain and reproducibility

- Module sources must be VERSION-PINNED - a registry version
  constraint or a git source with a ?ref= tag/commit. Flag any
  unpinned/version-less source: unpinned modules make builds
  non-reproducible and are a supply-chain exposure.
- Provider and terraform version constraints should be declared so
  validation is hermetic.

## Parameterization and defaults

- Regions, project ids, and sizing belong in variables with sane
  defaults, not hardcoded literals scattered through resources -
  hardcoding is a portability and review-diff hazard. (Judge dosage:
  a tiny single-purpose stack may reasonably inline values; flag
  hardcoding where it will clearly be copied or promoted.)
- Flag workloads placed on the pre-existing "default" VPC/subnetwork
  in anything production-shaped: auto-mode subnets and permissive
  default firewall rules are a known anti-pattern; expect a dedicated
  network with explicit firewall intent.

## Security posture in HCL

- No plaintext secrets in any value - connection strings, keys,
  passwords come from a secret manager reference, never a literal.
- Least-privilege identities: flag primitive roles (owner/editor) and
  service accounts shared across unrelated workloads.
- Expect CMEK where the archetype's data sensitivity calls for it, and
  private IP / restricted ingress for anything not deliberately
  public.
