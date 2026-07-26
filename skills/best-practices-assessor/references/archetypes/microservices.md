---
type: ArchetypeBestPractice  
title: Cloud Run in Microservices  
description: Describes how Cloud Run is configured for Microservices.  
timestamp: 2026-06-20T13:00:00Z  
tags: [archetypes, microservices, "product:cloud_run"]

---

# Cloud Run in Microservices

Cloud Run is the recommended default for **stateless, request, or event-driven
microservices**. Its serverless nature means developers focus solely on
containerized application code, benefiting from automatic scaling, traffic
management, and minimal operational burden.

## Best Practices & Configuration

*   **Scaling and Concurrency:** Autoscaling is based on traffic or CPU
    utilization, with rapid scale-out capability. Concurrency is configurable
    via `container_concurrency`.
*   **Networking Configuration (Direct VPC Egress):** For any Cloud Run service
    that must access private resources (databases, GKE ILBs, Memorystore),
    always configure it to use **Direct VPC Egress**. This isolates internal
    traffic from the public internet and replaces the legacy Serverless VPC
    Access Connector.

    ```hcl
    # Terraform example for Cloud Run with Direct VPC Egress
    resource "google_cloud_run_v2_service" "default" {
      name     = "my-service"
      location = "us-central1"

      template {
        vpc_access {
          network_interfaces {
            network    = "projects/my-project/global/networks/my-vpc"
            subnetwork = "projects/my-project/regions/us-central1/subnetworks/my-subnet"
          }
          egress = "PRIVATE_RANGES_ONLY"
        }
        # ...
      }
    }
    ```

*   **Multi-Container Support (Sidecar):** Cloud Run supports the **Sidecar
    pattern**. This is leveraged for observability (running the **OpenTelemetry
    Collector sidecar** to collect and export metrics/traces) and security
    (running the **Cloud SQL Auth proxy** sidecar for secure database
    connectivity).

*   **Workload Identity:** Use Workload Identity for service-to-service
    communication involving GCP APIs. Create a custom, least-privilege service
    account for each Cloud Run service and attach it, rather than using the
    default compute service account.

## Anti-Patterns

*   **Relying on Public Endpoints for Internal Calls:** Do not configure Cloud
    Run to call public endpoints of GKE services for internal communication. Use
    Direct VPC Egress instead.
*   **Hosting Databases directly on Cloud Run:** Resist the urge to host
    databases or large, durable caches directly on Cloud Run.

## Reference Architectures

*   **Serverless E-commerce API Backend:** Cloud Run with Cloud SQL, using
    Direct VPC Egress.
*   **Globally Distributed Low-Latency API:** Cloud Run in multiple regions,
    using Global HTTPS Load Balancer with Regional Serverless NEGs and Cloud
    CDN.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Pub/Sub in Microservices \
description: Describes how Cloud Pub/Sub is configured for Microservices. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, microservices, "product:pubsub"]

--------------------------------------------------------------------------------

# Cloud Pub/Sub in Microservices

Cloud Pub/Sub is widely used to decouple microservices and implement
asynchronous communication, which is central to event-driven architectures and
the Saga Choreography pattern.

## Best Practices & Configurations

*   **Asynchronous Communication:** Used as a reliable, highly scalable event
    broker. Cloud Run services often act as consumers via Push Subscriptions
    (webhooks), while GKE/MIGs may use either Push or Pull Subscriptions for
    greater control over message processing rates.
*   **Saga Choreography:** Each service publishes a unique domain event to
    Pub/Sub. Subscribing services act on these events to carry out distributed
    transactions.

## Anti-Patterns

*   **Failing to Implement Idempotency:** Designing event consumers that process
    messages without checking for duplicates. Pub/Sub guarantees at-least-once
    delivery, so non-idempotent processing can lead to data corruption or
    duplicate transactions. Always check a unique transaction ID before
    executing business logic.

## Reference Architectures

*   **Order Processing Saga Choreography:** Cloud Run and GKE Deployment
    utilizing Cloud Pub/Sub as an event-driven bus with idempotent
    subscriptions.
*   **Real-Time Fraud Detection Pipeline:** Cloud Run publisher sending events
    to Pub/Sub, which are pulled by a GKE subscriber.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: GKE in Microservices \
description: Describes how GKE is configured for Microservices. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, microservices, "product:gke"]

--------------------------------------------------------------------------------

# Google Kubernetes Engine (GKE) in Microservices

GKE is the platform of choice for workloads demanding deep infrastructure
control, specialized hardware, or stateful persistence.

## Best Practices & Configuration

*   **GKE Autopilot:** The recommended mode, as it automates cluster and node
    management (updates, scaling, patching), significantly lowering operational
    overhead.
*   **VPC-Native Clusters:** Always configure GKE clusters as VPC-native (using
    IP aliasing). This enables the cluster to use secondary IP ranges for Pods
    and Services, improving IP address management and scalability.
*   **Workload Identity:** The most crucial security configuration for GKE.
    Enabling Kubernetes Service Accounts to impersonate Google Service Accounts
    for secure, keyless access to GCP resources like Cloud SQL or Cloud Storage.

    ```hcl
    # Terraform example for enabling Workload Identity
    resource "google_container_cluster" "primary" {
      name               = "my-gke-cluster"
      location           = "us-central1"
      # ...
      workload_identity_config {
        workload_pool = "${var.project_id}.svc.id.goog"
      }
    }
    ```

*   **Stateful Configuration:** Deploy stateful applications (e.g., Redis Cache,
    Databases) using **StatefulSets** combined with `volumeClaimTemplates` to
    dynamically provision **PersistentVolumes** backed by Compute Engine
    Persistent Disks (PDs).

*   **Observability and Traffic Control (Service Mesh):** Deploy **Anthos/Cloud
    Service Mesh**. It provides automatic security (mTLS) and resilience
    (Circuit Breaking via Istio DestinationRules) outside of the application
    code through injected Envoy sidecars.

## Anti-Patterns

*   **Relying on Public Endpoints for Internal Calls:** Avoid exposing internal
    microservices on a public IP. Use Internal Load Balancers and Private
    Service Connect instead.
*   **Embedding Database Credentials in Containers:** Do not store database
    passwords in Kubernetes Secrets. Use Workload Identity to authenticate
    instead.

## Reference Architectures

*   **Hybrid E-commerce with Stateful Inventory:** Cloud Run (stateless)
    interacting with a GKE StatefulSet via an Internal Load Balancer.
*   **GKE Sidecar Pattern (Observability/Security):** Pods running the main app,
    Cloud SQL Auth Proxy sidecar, and Fluent Bit Log Forwarding.
