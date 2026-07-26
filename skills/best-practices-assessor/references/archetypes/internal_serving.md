---
type: ArchetypeBestPractice  
title: Compute Engine in Internal Serving  
description: Describes how Compute Engine is configured for Internal Serving.  
timestamp: 2026-06-20T13:00:00Z  
tags: [archetypes, internal_serving, "product:compute_engine"]

---

# Compute Engine

**Compute Engine** offers IaaS, providing maximum control over virtual machines,
suitable for lift-and-shift or highly customized environments, relying on
internal DNS and firewall rules for internal communication.

## Usage

*   Typically deployed in Managed Instance Groups (MIGs) and placed behind an
    Internal Application Load Balancer.
*   Often used for data processing tasks, legacy monolithic applications, or
    applications requiring specific OS or kernel configurations.

## Best Practices

*   **Private Google Access:** For internal services on Compute Engine to
    securely access Google APIs (like BigQuery or Cloud Storage) without
    traversing the public internet, Private Google Access and specific DNS
    configurations are essential.
*   Use internal IPs and Internal Load Balancers rather than external IPs for
    internal workloads.

## Anti-patterns

*   Assigning external IP addresses to Compute Engine instances serving purely
    internal workloads.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: GKE in Internal Serving \
description: Describes how Google Kubernetes Engine (GKE) is configured for
Internal Serving. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, internal_serving, "product:gke"]

--------------------------------------------------------------------------------

# Google Kubernetes Engine (GKE)

**Google Kubernetes Engine (GKE)** is a managed Kubernetes environment for
complex microservices and stateful applications, offering fine-grained control
and advanced networking. It integrates with internal LoadBalancer Services and
Ingress.

## Usage

*   Often used to host backend microservices, while Cloud Run or API Gateways
    act as frontends.
*   Integrates with Internal Application Load Balancers via Ingress or the
    Kubernetes Gateway API.
*   **Workload Identity:** GKE Workload Identity Federation binds Kubernetes
    Service Accounts (KSAs) to Google Cloud Service Accounts (GSAs) to
    authenticate against other GCP services securely.

## Best Practices

*   **Bulkhead Pattern:** Logically separate critical internal services into
    dedicated Kubernetes Namespaces and physically isolate their compute
    resources using dedicated GKE Node Pools. This is further enforced by
    Kubernetes Resource Quotas and node taints/tolerations to prevent cascading
    failures.

## Anti-patterns

*   **External exposure:** Directly exposing GKE services with external Load
    Balancers when internal-only access is required. This inadvertently exposes
    internal services to the public internet. Use internal application load
    balancers instead.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Run in Internal Serving \
description: Describes how Cloud Run is configured for Internal Serving. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, internal_serving, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run

**Cloud Run** is a fully managed serverless platform ideal for stateless,
event-driven internal services, offering automatic scaling to zero, pay-per-use
billing, and built-in ingress control for internal traffic.

## Usage

*   Often used as a frontend secured by Identity-Aware Proxy (IAP) or as a
    high-throughput/event-driven internal API.
*   Uses Direct VPC Egress or Serverless VPC Access to connect to internal
    resources (Internal Load Balancers, Cloud SQL via private IPs, Memorystore,
    etc.).

## Best Practices

*   **Direct VPC Egress:** Use Direct VPC Egress for a simpler, more performant,
    and cost-effective approach within the same VPC, where Cloud Run instances
    receive internal IPs directly, eliminating intermediate connector hops.
*   Restrict ingress to `internal` or `internal-and-cloud-load-balancing` for
    internal serving components.

## Anti-patterns

*   Leaving the `run.app` URL publicly accessible when the service is intended
    to be internal-only, even if IAP is enabled, can create potential bypasses.
    Proper ingress controls or disabling the auto-assigned URL are crucial.
*   Connecting Cloud Run services to Cloud SQL databases using public IP
    addresses. Use Direct VPC Egress or Private Service Connect instead.
