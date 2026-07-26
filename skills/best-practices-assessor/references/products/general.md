---
type: PerProductBestPractice  
title: Terraform Service Account Impersonation  
description: Use service account impersonation for Terraform operations instead of static keys.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, mlops_lifecycle]

---

# Terraform Service Account Impersonation

Use service account impersonation for Terraform operations instead of static
keys.

## Guidelines

*   **Secure Impersonation:** Use service account impersonation
    (`impersonate_service_account` in the provider configuration) for Terraform
    operations instead of downloading long-lived access keys.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Concurrency \
description: Optimize Cloud Functions Gen 2 concurrency settings. \
timestamp: 2026-06-21T15:05:00Z \
tags: [best_practices, performance]

--------------------------------------------------------------------------------

# Cloud Functions Concurrency

Cloud Functions Gen 2 supports concurrent request handling (up to 1000 requests
per instance). This drastically reduces the number of cold starts, lowers
compute costs, and prevents database connection pool exhaustion compared to Gen
1's single-concurrency model. Configure `max_instance_request_concurrency` via
Terraform to leverage this capability.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Compute Sizing \
description: Provision optimal memory and CPU for Cloud Functions Gen 2. \
timestamp: 2026-06-21T15:05:00Z \
tags: [best_practices, performance]

--------------------------------------------------------------------------------

# Cloud Functions Compute Sizing

Gen 2 supports up to 32 GB RAM and 8 vCPUs. For CPU-bound tasks, provisioning
larger compute blocks can lower the total serverless bill by radically dropping
the execution duration. Ensure `available_memory` is at least 3-4x the payload
size if using the `/tmp` directory to avoid OOM crashes.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Timeouts \
description: Manage execution timeouts for Cloud Functions. \
timestamp: 2026-06-21T15:05:00Z \
tags: [best_practices, performance]

--------------------------------------------------------------------------------

# Cloud Functions Timeouts

Functions have a maximum execution time (up to 60 minutes for Gen 2 HTTP, 9
minutes for background events). Configure this duration based on the workload
requirements. Long-running tasks that exceed these should be migrated to Cloud
Run Jobs or decoupled.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Scaling Limits \
description: Configure minimum and maximum instances for Cloud Functions. \
timestamp: 2026-06-21T15:05:00Z \
tags: [best_practices, performance]

--------------------------------------------------------------------------------

# Cloud Functions Scaling Limits

*   **Minimum Instances (`min_instance_count`):** Mitigate cold starts for
    critical user-facing APIs by keeping container instances warm and active in
    memory. Reduces API latency to milliseconds but incurs persistent idle
    compute costs.
*   **Maximum Instances (`max_instance_count`):** Prevents runaway billing and
    downstream database connection exhaustion. Acts as a hard ceiling during
    DDoS attacks or infinite loops.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Build Security \
description: Use private worker pools and Artifact Registry lifecycle policies.
\
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security]

--------------------------------------------------------------------------------

# Cloud Functions Build Security

*   **Custom Worker Pools:** Run container builds on a private worker pool with
    `no_external_ip = true` to completely isolate the compilation phase from the
    public internet.
*   **Artifact Registry Lifecycle:** Configure a custom `docker_repository` to
    enable lifecycle policies that purge untagged images automatically,
    preventing storage sprawl and reducing costs.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Secret Management \
description: Inject secrets using Secret Manager. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security]

--------------------------------------------------------------------------------

# Cloud Functions Secret Management

Inject secrets at startup using Secret Manager (`secret_environment_variables`).
Pin secrets to a specific version (e.g., `version = "1"`) to prevent drift
across instances. For multi-line TLS certificates, mount them as files in a
`tmpfs` using `secret_volumes` with `version = "latest"` to allow hot-reloading.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Audit Logging \
description: Enable Data Access audit logs for accountability. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security]

--------------------------------------------------------------------------------

# Audit Logging

Enable Data Access audit logs for model execution and vector database querying
to track security posture and ensure accountability.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions IAM and Identity \
description: Use User-Managed Service Accounts and require authentication. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security]

--------------------------------------------------------------------------------

# Cloud Functions IAM and Identity

*   **Principle of Least Privilege:** Override the permissive default service
    accounts by specifying a dedicated User-Managed Service Account
    (`service_account_email`) with precise IAM roles limiting its blast radius.
*   **Authentication:** Gen 2 functions require authentication. Do not grant
    `roles/cloudfunctions.invoker` or `roles/run.invoker` to `allUsers` unless
    building a public webhook.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Network Perimeter \
description: Configure ingress and egress controls for Cloud Functions. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security]

--------------------------------------------------------------------------------

# Cloud Functions Network Perimeter

*   **Ingress Controls:** Do not expose Cloud Functions directly to the public
    internet using default `.run.app` URLs if they are internal APIs. Set
    `ingress_settings = "ALLOW_INTERNAL_AND_GCLB"` to force traffic through a
    Global External HTTP(S) Load Balancer, enabling Cloud Armor (WAF) and
    Identity-Aware Proxy (IAP).
*   **Egress Controls:** To connect to internal enterprise databases, use
    Serverless VPC Access Connectors or Direct VPC Egress. Setting egress to
    `ALL_TRAFFIC` forces public-bound internet requests through the VPC,
    allowing them to exit via Cloud NAT with a static IP address that can be
    allowlisted by external systems.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Asynchronous Decoupling \
description: Leverage asynchronous decoupling instead of synchronous HTTP
function chaining. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, observability]

--------------------------------------------------------------------------------

# Cloud Functions Asynchronous Decoupling

Avoid synchronous function chaining (e.g., configuring Function A to call
Function B directly via HTTP/REST or gRPC and wait for a response). This is a
known bad architecture pattern that creates tight coupling, increases latency
(total request time is the sum of all service response times), and risks
cascading failures—if the downstream service is slow or down, the calling
function hangs, consumes resources, and eventually times out.

Instead, leverage asynchronous decoupling. Configure the architecture so that
the initial function publishes an event to a Cloud Pub/Sub topic and immediately
returns a success status. This ensures the publisher does not need to know which
or how many services are consuming the event, prevents the "thundering herd"
problem, and allows the downstream Cloud Function to process the message at a
rate it can handle whenever it is available.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Max Instance Count \
description: Define a strict max_instance_count ceiling to prevent database
connection pool exhaustion and control scaling. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, observability]

--------------------------------------------------------------------------------

# Cloud Functions Max Instance Count

Define a strict `max_instance_count` ceiling in your function configuration.
This prevents a sudden spike of requests from opening too many connections and
crashing traditional databases. It also acts as a cost-control measure to
prevent runaway scaling.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Dead-Letter Queues (DLQ) \
description: Configure a DLQ on the underlying Pub/Sub subscription for
event-driven functions. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, observability]

--------------------------------------------------------------------------------

# Cloud Functions Dead-Letter Queues (DLQ)

Always configure a Dead-Letter Queue (DLQ) on the underlying Pub/Sub
subscription. If an unparseable "poison pill" payload causes deterministic
failures, the DLQ intercepts the message, preventing infinite retry storms that
cause runaway billing.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions OpenTelemetry Configuration \
description: Inject OpenTelemetry configurations via environment variables to
correlate logs to Cloud Trace. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, observability]

--------------------------------------------------------------------------------

# Cloud Functions OpenTelemetry Configuration

Inject OpenTelemetry configurations (e.g.,
`OTEL_PROPAGATORS="tracecontext,gcp"`) as environment variables to automatically
correlate stdout logs to Cloud Trace execution paths.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions Hash-Based Object Deployments \
description: Use hash-based object deployments to guarantee deterministic
deployments and preserve historical artifacts. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, observability]

--------------------------------------------------------------------------------

# Cloud Functions Hash-Based Object Deployments

Never configure Terraform to deploy a static ZIP filename. Use hash-based object
deployments. Compute the MD5/SHA256 hash of the zipped source code locally and
append it to the Cloud Storage object name. This guarantees deployments only
occur when code changes and preserves historical artifacts for instantaneous
rollbacks.
