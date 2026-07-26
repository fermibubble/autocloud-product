---
type: PerProductBestPractice
title: Serverless Compute Cost Optimization
description: Leverage scale-to-zero capabilities in Cloud Run and Agent Engine.
timestamp: 2026-06-25T14:25:24Z
tags: [best_practices, cost_optimization, "product:cloud_run", "product:agent_engine"]

---

# Serverless Compute Cost Optimization

Leverage Vertex AI Agent Engine (Reasoning Engine) or Cloud Run rather than GKE
for workloads with sporadic, variable, or low-throughput inference patterns.
Both runtimes support scaling down to zero instances, eliminating baseline idle
compute costs.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud CDN for Static Content \
description: Deliver static content efficiently using Cloud CDN. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, performance, "product:cloud_cdn", "product:cloud_run",
"product:gke"]

--------------------------------------------------------------------------------

# Cloud CDN for Static Content

Front all static storage origins (like GCS buckets hosting SPAs/assets or
Compute Engine instance groups) with Cloud CDN to cache assets close to users.

This solves several issues by accelerating the delivery of web and video content
(such as HTML, CSS, JavaScript, and images). By serving content from edge caches
close to users, Cloud CDN reduces latency, lowers the load on your origin
servers, and decreases network delivery costs. It is recommended to use the
default `CACHE_ALL_STATIC` cache mode to automatically identify and cache common
static content types.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Centralized Cache for Serverless \
description: Use Memorystore for caching in serverless environments. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, performance, "product:memorystore", "product:cloud_run"]

--------------------------------------------------------------------------------

# Centralized Cache for Serverless

Do not rely on local, ephemeral container file systems for caching or
Incremental Static Regeneration (ISR) on serverless runtimes (like Cloud Run).
Instead, provision and use a centralized, shared cache like Memorystore (Redis)
to maintain page cache consistency as container instances scale up and down.

Using Memorystore as a caching layer for Cloud Run services solves the problem
of high latency and improves responsiveness by caching frequently accessed
database queries, session data, or user preferences. Since Cloud Run is a
managed serverless environment, you must configure Direct VPC egress
(recommended for lower latency and costs) or a Serverless VPC Access connector
to bridge connectivity to the VPC network where the Memorystore instance
resides.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Private IPs for Compute \
description: Connect compute backends using private IPs. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:gke", "product:cloud_run"]

--------------------------------------------------------------------------------

# Private IPs for Compute

Connect compute backends (Cloud Run, GKE) to prediction endpoints and storage
components using private IPs. Do not route internal AI traffic over the public
internet.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Custom Service Accounts and Granular IAM \
description: Provision dedicated service accounts with granular IAM roles. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:gke", "product:cloud_run",
"product:vertex_ai", "product:dataflow"]

--------------------------------------------------------------------------------

# Custom Service Accounts and Granular IAM

*   **Custom Service Accounts:** Never use the default Compute Engine or App
    Engine service accounts for running ML workloads (Vertex AI Training, GKE
    worker nodes, Dataflow pipelines, or Cloud Run containers).
*   **Granular IAM Roles:** Provision dedicated, user-managed service accounts
    with the absolute minimum required roles (e.g., `roles/dataflow.worker` at
    the project level, combined with specific `Storage Object Viewer` or
    `Storage Object Creator` roles on target GCS buckets, and
    `bigquery.dataEditor` on target datasets).

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Restrict Ingress on Public Compute \
description: Disable default run.app URLs to prevent bypass of Cloud Armor. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:cloud_run"]

--------------------------------------------------------------------------------

# Restrict Ingress on Public Compute

For Cloud Run services behind an External Load Balancer, configure ingress
settings to `INGRESS_TRAFFIC_INTERNAL_AND_CLOUD_LOAD_BALANCING` and disable
default `run.app` URLs to prevent bypass of Cloud Armor protection.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Workload Health Checks & Probes \
description: Configure explicit probes for Cloud Run and GKE. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:gke", "product:cloud_run"]

--------------------------------------------------------------------------------

# Workload Health Checks & Probes

Configure explicit startup and readiness probes for Cloud Run services, and
liveness/readiness probes for GKE pods, to ensure the load balancer only routes
requests to fully initialized, healthy instances.

### Terraform Syntax Guidelines for Cloud Run Probes:

*   **Cloud Run v1 (`google_cloud_run_service`)**: Ensure `liveness_probe` or
    `startup_probe` block is declared inside `template.spec.containers`:

    ```terraform
    liveness_probe {
      http_get {
        path = "/healthz"
      }
      initial_delay_seconds = 10
    }
    ```

*   **Cloud Run v2 (`google_cloud_run_v2_service`)**: Ensure `liveness_probe` or
    `startup_probe` block is declared inside `template.containers`:

    ```terraform
    liveness_probe {
      http_get {
        path = "/healthz"
      }
    }
    ```

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Run in Scheduled and Orchestration \
description: Describes how Cloud Run is configured for Scheduled and
Orchestration. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, scheduled_and_orchestration, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Scheduled and Orchestration

Cloud Run serves as the "Agent" for longer or more complex discrete tasks within
the archetype. It is a serverless platform running custom containerized
applications and is preferred for services needing custom runtimes or longer
execution times (via Cloud Run Jobs).

## Role and Integration

*   **Invocation:** Cloud Workflows, Cloud Scheduler, and Pub/Sub can all
    trigger Cloud Run services. Workflows can invoke Cloud Run endpoints
    securely.
*   **Private Services:** Workflows can resolve and invoke private Cloud Run
    services (ingress set to 'internal traffic only') using Service Directory.

## Best Practices

*   **Idempotency:** Like Cloud Functions, Cloud Run services must be designed
    to be idempotent to handle the "at least once" delivery mechanisms of
    Scheduler and Pub/Sub. Use unique event IDs or transaction checks.
*   **Unified Observability:** Ensure structured JSON logging is used and that
    `traceparent` headers are propagated through Cloud Run to enable end-to-end
    distributed tracing across the scheduled automation system.

## Anti-Patterns

*   **Lack of Idempotency:** Not checking if a task has already been processed
    before mutating state or performing actions.
*   **Synchronous Service Chaining:** Coupling multiple Cloud Run microservices
    via direct synchronous HTTP calls instead of using Pub/Sub for choreography
    or Workflows for orchestration.

## Reference Architecture

*   **Scheduler-Agent-Supervisor:** Cloud Run acts as the Report Agent,
    generating a long-running report. It updates its state in Firestore. A
    Supervisor workflow monitors Firestore for stalled agents and re-triggers
    them if necessary.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Run in Event-Driven Architectures \
description: Describes how Cloud Run is integrated and configured as an event
consumer (sink) in the Event-Driven archetype. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, event_driven, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Event-Driven Architectures

Describes how Cloud Run is integrated and configured as an event consumer (sink)
in the Event-Driven archetype.

## Integration Details

In Event-Driven Architectures, Cloud Run hosts the stateless business logic that
reacts to events routed by Pub/Sub or Eventarc. It utilizes automated HTTP
endpoints (for push subscriptions) or client libraries (for pull subscriptions)
to process messages. Scale-to-zero compute minimizes idle cost, while rapid
autoscaling handles high-volume traffic bursts.

## Target Configurations

### 1. Push Ingestion (Recommended Baseline)

The default configuration where Pub/Sub or Eventarc delivers events via HTTP
POST requests.

*   **Authentication:** Requires the incoming request to carry a Google-signed
    OIDC JWT, and the routing service's identity must hold the
    `roles/run.invoker` role on the Cloud Run service.

### 2. Ingestion in VPC Service Controls (VPC-SC) Perimeters

When a service is protected within a VPC Service Controls (VPC-SC) perimeter,
push subscriptions to Cloud Run are supported by configuring proper VPC-SC
ingress rules.

*   **Solution:** Configure the VPC-SC perimeter ingress rules to allow the
    Pub/Sub service account to invoke the Cloud Run service, enabling secure
    HTTP push delivery.

### 3. Direct VPC Egress for Database/Cache Access

If the consumer needs to mutate private backend state (e.g., writing clickstream
profile updates to Cloud Memorystore for Redis or Cloud SQL using private IPs),
it must utilize Serverless VPC Access or Direct VPC Egress.

*   **Recommendation:** Direct VPC Egress is preferred for lower latency and
    simpler setup.

### 4. Idempotent Processing

Given Pub/Sub's at-least-once delivery guarantee, Cloud Run services must be
designed for idempotency.

*   **Pattern:** Perform a transactional check against a database (e.g.,
    Firestore) using the event's unique ID to ensure the event has not been
    processed previously.

## Infrastructure Code (Terraform)

### Private Cloud Run Event Consumer with Direct VPC Egress

```terraform
# Service Account for Cloud Run Service
resource "google_service_account" "run_sa" {
  account_id   = "cloud-run-consumer-sa"
  display_name = "Cloud Run Consumer Service Account"
}

# Private Cloud Run Service configured to receive internal traffic only
resource "google_cloud_run_v2_service" "event_consumer" {
  name     = "event-consumer-service"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.run_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 50
    }

    containers {
      image = "gcr.io/my-project/my-consumer-app:latest"
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }

    # Direct VPC Egress for private database connectivity
    vpc_access {
      network_interfaces {
        network    = "projects/my-project/global/networks/my-vpc"
        subnetwork = "projects/my-project/regions/us-central1/subnetworks/my-subnet"
      }
      egress = "ALL_TRAFFIC"
    }
  }
}
```

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Run in Microservices \
description: Describes how Cloud Run is configured for Microservices. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, microservices, "product:cloud_run"]

--------------------------------------------------------------------------------

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

type: PerProductBestPractice \
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

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Run in Web Applications \
description: Describes how Cloud Run is integrated and configured for Web
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Web Applications

Describes how Cloud Run is integrated and configured for Web Applications.

## Integration Details

In Web Applications, Cloud Run is usually exposed behind an Application Load
Balancer via a Serverless Network Endpoint Group (NEG). This allows developers
to serve containerized frontends and backends with SSL termination, CDN caching,
and custom domain routing.

## Target Configurations

### Private Microservice with Direct VPC Egress

Configuring Cloud Run to reside inside a VPC network using Direct VPC Egress for
secure database/cache access, and setting the ingress level to
`INGRESS_TRAFFIC_INTERNAL_ONLY` to restrict public access.
Invoker permissions (`roles/run.invoker`) should only be given to specific
principals or groups.

## Infrastructure Code (Terraform)

### Private Microservice with Direct VPC Egress

```terraform
resource "google_cloud_run_v2_service" "private_service" {
  name     = "internal-service"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "gcr.io/my-project/db-processor:latest"
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }

    vpc_access {
      network_interfaces {
        network    = "projects/my-project/global/networks/my-vpc"
        subnetwork = "projects/my-project/regions/us-central1/subnetworks/my-subnet"
      }
      egress = "ALL_TRAFFIC" # Route all outbound traffic through the VPC
    }

    service_account = "internal-service-sa@your-project.iam.gserviceaccount.com"
  }
}
```

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Run in Private Data \
description: Describes how Cloud Run is configured for Private Data. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, private_data, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Private Data

**Usage:** Serverless platform for processing applications, such as a
telemedicine backend or secure HR payroll systems.

**Best Practices:**

-   Achieve isolation and private access using **Serverless VPC Access
    connectors** (or Direct VPC Egress).
-   Route all outbound traffic into a dedicated subnet within the customer's
    VPC.
-   Communicate privately with Cloud SQL, Memorystore, and other internal
    resources using internal IPs.
