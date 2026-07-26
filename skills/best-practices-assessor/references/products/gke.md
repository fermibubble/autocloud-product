---
type: PerProductBestPractice  
title: GKE Autopilot  
description: Deploy workloads to GKE Autopilot for pod-level resource billing.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, cost_optimization, "product:gke"]

---

# GKE Autopilot

Deploy workloads to GKE Autopilot for pod-level resource billing. This avoids
paying for system overhead or unallocated space on expensive GPU nodes.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Node Auto-Provisioning (NAP) \
description: Enable Node Auto-Provisioning to dynamically spawn or tear down
node pools. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# GKE Node Auto-Provisioning (NAP)

Enable NAP to dynamically spawn or tear down node pools that exactly match pod
hardware constraints (e.g. specific GPU type and memory).

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Multi-Instance GPU (MIG) on GKE \
description: Partition large NVIDIA A100 or H100 GPUs into smaller isolated
slices. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# Multi-Instance GPU (MIG) on GKE

Partition large NVIDIA A100 or H100 GPUs into up to 7 independent
hardware-isolated slices. This allows multiple smaller inference pods to run on
a single physical GPU, preventing hardware underutilization.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Dynamic Workload Scheduling (DWS) \
description: Use DWS Flex-start model for batch jobs to prevent partial-cluster
idling. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# GKE Dynamic Workload Scheduling (DWS)

Use DWS Flex-start model (via `ProvisioningRequest`) for batch jobs. DWS waits
until the entire requested pool of GPUs is available before launching the job,
preventing "partial-cluster idling".

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: NVIDIA MPS on GKE \
description: Set up Multi-Process Service (MPS) to share execution scheduling. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# NVIDIA MPS on GKE

Set up Multi-Process Service (MPS) to share execution scheduling and memory
boundaries across replicas of the same model.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GPU Time-Sharing on GKE \
description: Enable time-sharing to allow multiple containers to execute
concurrently. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# GPU Time-Sharing on GKE

For development environments or low-throughput inference endpoints, enable
time-sharing to allow multiple containers to execute concurrently via context
switching on a single GPU.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Spot VMs on GKE \
description: Leverage Spot VMs for fault-tolerant workloads to achieve cost
savings. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# Spot VMs on GKE

Leverage Spot VMs for fault-tolerant workloads, such as distributed training
with regular checkpointing or asynchronous batch processing, to achieve up to
91% cost savings compared to on-demand VMs.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Cluster Autoscaler Profile \
description: Configure GKE Cluster Autoscaler to use the optimize-utilization
profile. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:gke"]

--------------------------------------------------------------------------------

# GKE Cluster Autoscaler Profile

Configure GKE Cluster Autoscaler to use the **`optimize-utilization`** profile
instead of `balanced` to aggressively remove unused accelerator nodes when idle.

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
title: Cloud Storage FUSE Caching \
description: Accelerate model weight loading using GCS FUSE Anywhere Cache. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, performance, "product:gcs_storage", "product:gke"]

--------------------------------------------------------------------------------

# Cloud Storage FUSE Caching

Mount Cloud Storage buckets as local file systems on worker nodes for fast,
parallel model weight downloading. Configure and enable **Anywhere Cache** to
speed up cold starts for AI/ML workloads.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: AI-Aware Load Balancing \
description: Intelligent AI-aware routing for inference endpoints using GKE
Inference Gateway. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, performance, "product:gke", "product:vertex_ai"]

--------------------------------------------------------------------------------

# AI-Aware Load Balancing

For self-hosted LLM serving, avoid standard Layer 7 round-robin load balancing.
Instead, configure and use the **GKE Inference Gateway** to intelligently manage
inference traffic.

The GKE Inference Gateway solves the complexities of deploying, managing, and
routing generative AI and machine learning inference workloads. It makes smart,
load-aware, and context-aware routing decisions to land requests on the
best-suited accelerator (GPU/TPU) for the job, and supports advanced techniques
like prefix caching to accelerate performance. Furthermore, utilizing a
multi-cluster GKE Inference Gateway allows you to pool accelerator resources
across multiple GKE clusters and regions, preventing resource silos, providing
fault tolerance during regional outages, and enabling bursting beyond the
capacity of a single cluster.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Global Model Deployments \
description: Deploy and failover inference endpoints globally. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, performance, "product:gke", "product:vertex_ai"]

--------------------------------------------------------------------------------

# Global Model Deployments

*   **Globally Distributed Deployments:** Deploy serving endpoints (Vertex AI
    Endpoints or GKE clusters) across multiple geographical GCP regions.
*   **Global Failover:** Route traffic using Global Cloud Load Balancing or
    Multi-cluster GKE Gateway to direct queries to the nearest healthy replica.
    This reduces geographical latency and ensures automated failover during
    regional or zonal outages. Note that Vertex AI Endpoints require a proxy
    (such as Cloud Run or Apigee) to attach to GCLB.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: KV Cache & Queue Depth Routing \
description: Optimize TTFT by routing based on cache and queue length. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, performance, "product:gke", "product:vertex_ai"]

--------------------------------------------------------------------------------

# KV Cache & Queue Depth Routing

Configure the GKE Inference Gateway to route requests based on real-time metrics
including KV cache utilization and active queue length on serving replicas. This
reduces Time to First Token (TTFT) and prevents node overload.

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
title: Model Armor Content Sanitization \
description: Content sanitization using Model Armor at the Gateway layer. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:model_armor", "product:vertex_ai",
"product:gke"]

--------------------------------------------------------------------------------

# Model Armor Content Sanitization

*   **Inline Filtering:** Integrate Model Armor inline in the serving pipeline
    (at the GKE Gateway layer) to screen all natural-language prompts and
    responses.
*   **Threat Mitigation:** Use customized templates to detect and block prompt
    injection, jailbreaks, malicious URLs, and sensitive data leakage (PII/PHI)
    using Google's Sensitive Data Protection (DLP) engine.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Minimizing GKE Workload Disruption \
description: Use PDBs, graceful termination, and node upgrade strategies. \
timestamp: 2026-06-20T15:35:00Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# Minimizing GKE Workload Disruption

*   **Set Tolerance for Disruption:** Configure Pod Disruption Budgets (PDBs) to
    ensure workloads maintain sufficient redundancy against voluntary
    disruptions.
*   **Node Upgrade Strategies:** For Standard clusters, choose a node upgrade
    strategy (surge or blue-green) that balances speed, workload disruption,
    risk mitigation, and cost.
*   **Capacity-Constrained and Stateful Workloads:** Leverage GCP *reservations*
    for node upgrades in resource-constrained environments to prevent capacity
    issues during surge upgrades.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Maintenance Windows & Exclusions \
description: Manage GKE maintenance windows to ensure smooth rollouts. \
timestamp: 2026-06-20T15:35:00Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# GKE Maintenance Windows & Exclusions

*   **Avoid Maintenance Windows for Compliant Rollouts:** For fleets operating
    under strict Change Management principles, **do not use maintenance
    windows**. Allowing GKE to enact a compliant wave rollout without
    maintenance windows ensures changes are made progressively.
*   **Maintenance Exclusions for Incident Response:** If an upgrade causes
    issues, set up a "no upgrades" Maintenance exclusion (maximum 30 days) on
    the production fleet via Terraform to limit impact until the cluster is
    stabilized.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Release Channels \
description: Choose the appropriate GKE release channel for your clusters. \
timestamp: 2026-06-20T15:35:00Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# GKE Release Channels

*   **Choose the Right Release Channel:** For standard production fleets, use
    the `Regular` release channel to balance stability and feature availability.
*   **FedRAMP Compliance:** For products in scope for FedRAMP, enable
    **Accelerated Upgrades** in the Regular channel. Note: If using a Canary
    cluster in the Rapid channel, Accelerated Patch Upgrades should be
    *disabled* on the Canary to minimize the number of versions being qualified.
*   **Canary Release Channel:** Enroll canary clusters in the `Rapid` release
    channel to receive the earliest possible detection of possible issues.
*   **Long-Term Support:** Use the `Extended` release channel for clusters that
    require long-term support for a minor version (up to 24 months). To use this
    channel effectively, you must perform two successive minor version upgrades
    one or two times per year.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Rollout Sequencing & Canary \
description: Sequence GKE upgrades and set up canary environments. \
timestamp: 2026-06-20T15:35:00Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# GKE Rollout Sequencing & Canary

*   **Rollout Sequencing:** Sequence upgrades globally instead of rolling out
    fleets simultaneously. Group clusters logically (e.g., dev, staging, canary,
    prod-region1, prod-region2) and let GKE sequence the rollouts. Wait at least
    several days between environments.
*   **Upgrade Visibility & Notifications:** Enable cluster notifications via
    Cloud Logging or Pub/Sub to proactively stay informed about upcoming
    scheduled cluster upgrade events.
*   **Canary Requirements:** Ensure your Canary clusters have production-parity,
    have auto-upgrades enabled without maintenance exclusions, and serve a small
    percentage of production traffic.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Critical Dependencies \
description: Architect critical dependencies like Artifact Registry and Load
Balancing for resilience. \
timestamp: 2026-06-20T15:35:00Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# GKE Critical Dependencies

*   **Container Images:** GKE uses Artifact Registry (AR) to serve system
    container images, which is regional. Configure workload containers and
    infrastructure to use regional Artifact Registries.
*   **Logging:** Use high throughput logging for the data plane if default
    throughput is insufficient.
*   **Load Balancing:** K8s ingress via Google Cloud Load Balancer (GCLB) is
    inherently global. Plan for global redundancy and failover.

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

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Connection-Draining & Capacity Routing \
description: Enforce connection-draining and capacity-based routing. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:gke", "product:compute_engine"]

--------------------------------------------------------------------------------

# Connection-Draining & Capacity Routing

For long-lived, multi-modal streaming protocols (such as WebSockets in Gemini
Live duplex connections) and extended inference queuing, shift away from
round-robin or latency-based distribution. Enforce connection-draining and
capacity-based routing at the traffic management layers to prevent replica
overloading.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Kubernetes Memory Alignments \
description: Configure CPU and Memory requests to equal limits on GKE. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# Kubernetes Memory Alignments

Set CPU/Memory requests equal to limits on Kubernetes/GKE workloads to guarantee
node scheduling stability and prevent Out Of Memory (OOM) kills. This should be
explicitly defined in your Kubernetes manifests or Terraform configurations.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Regional Clusters & Resilience \
description: Use regional clusters to handle zonal and regional infrastructure
outages. \
timestamp: 2026-06-20T15:35:00Z \
tags: [best_practices, reliability, "product:gke"]

--------------------------------------------------------------------------------

# GKE Regional Clusters & Resilience

*   **Zonal Infrastructure Outage:** Use regional clusters so the control plane
    is highly available. For GKE Standard, ensure node pools are spread across
    multiple zones in Terraform.
*   **Regional Infrastructure Outage:** Run multiple clusters in different
    regions. Use a multi-cluster load balancer that spans across regions so that
    traffic fails away from the unavailable region and routes to remaining
    regions.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE Monitoring Alerts \
description: Implement recommended alerts for GKE data plane and control plane
health. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, observability, "product:gke"]

--------------------------------------------------------------------------------

# GKE Monitoring Alerts

Implement GKE's recommended alerts and utilize the query library to set up
robust monitoring for data plane and control plane health using Infrastructure
as Code.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: GKE in AI/ML Applications \
description: GKE configurations, hardware choices, and networking options for
running high-performance AI/ML workloads. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, ai_ml, "product:gke"]

--------------------------------------------------------------------------------

# GKE in AI/ML Applications

Describes how Google Kubernetes Engine (GKE) is customized and configured for
running high-performance AI/ML workloads.

## Integration Details

For AI/ML applications, GKE is configured with accelerator-optimized node pools
(GPUs or TPUs), multi-networking configurations, and high-performance storage
drivers to optimize training and inference throughput.

## Target Configurations

### 1. Accelerator-Optimized Machine Types

Configure node pools with specialized VM families to match workload profiles:

*   **G2 VMs (NVIDIA L4):** Cost-effective, ideal for low-to-medium complexity
    inference and training.
*   **A2 VMs (NVIDIA A100):** High memory capacity, standard for large model
    training.
*   **A3 High/Mega/Ultra (NVIDIA H100/H200):** Ultra-performance training and
    serving. A3 Mega provides 1600 Gbps network bandwidth; A3 Ultra includes
    H200 GPUs and Titanium ML adapters.
*   **A4 VMs (NVIDIA Blackwell B200):** Next-generation scale for trillions of
    parameters.
*   **TPU Node Pools:** TPU v5e (price-performance inference/training) and
    Trillium TPU v6e (up to 4.7x peak compute increase).

### 2. GPU Sharing Configurations

Maximize GPU utilization across smaller inference pods:

*   **Multi-Instance GPU (MIG):** Hard partitioning of A100/H100 GPUs into up to
    7 isolated virtual GPUs.
*   **NVIDIA MPS:** Concurrent execution sharing of execution scheduling and
    memory boundaries.
*   **GPU Time-Sharing:** Context-switching for non-prod or low-throughput
    endpoints.

### 3. High-Performance Storage Integration

*   **Hyperdisk ML:** Read-only block storage volume that can be attached to up
    to 2,500 pods simultaneously, delivering 1.2 TB/s aggregate throughput to
    eliminate model weight loading bottlenecks.
*   **Cloud Storage FUSE:** CSI driver that mounts GCS buckets directly as local
    folder paths on pods. Pair with **Anywhere Cache** to speed up scale-up.

### 4. Multi-Networking & GPUDirect

*   **GKE Multi-Networking:** Enables provisioning up to 9 NICs per pod (1
    control plane, 8 data plane subnets).
*   **GPUDirect TCPX/RDMA:** Bypasses host CPU, allowing direct GPU-to-NIC
    communication to maximize bandwidth during training synchronization.

### 5. Kubernetes Orchestration APIs

*   **JobSet API:** Groups and coordinates PyTorch/JAX worker pods. Restarts the
    entire JobSet if a single pod fails to maintain sync.
*   **LeaderWorkerSet API:** Used for distributed multi-GPU serving. Coordinates
    a leader pod and worker pods (e.g. for vLLM).
*   **Kueue:** Manages job queuing, prioritizations, and fair-share allocation
    of accelerators across teams.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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

type: PerProductBestPractice \
title: GKE in Web Applications \
description: Describes how Google Kubernetes Engine (GKE) is integrated and
configured for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:gke"]

--------------------------------------------------------------------------------

# GKE in Web Applications

Describes how Google Kubernetes Engine (GKE) is integrated and configured for
Web Applications.

## Integration Details

For Web Applications, Google Kubernetes Engine (GKE) serves as a robust
container orchestration platform suitable for complex microservices-based
full-stack architectures, API gateways, and stateful applications. It offers
maximum control over cluster networking, container scheduling, and resource
allocation. GKE is exposed to user traffic via GKE Ingress, which provisions an
External Application Load Balancer.

## Target Configurations

### 1. Web Application Fronted by GKE Ingress & IAP

Configuring GKE Ingress to manage routing to stateless pods, fronted by
Identity-Aware Proxy (IAP) for user authentication.

### 2. Private GKE Connection to Cloud SQL via Proxy Sidecar

Enabling pods in a private, VPC-native GKE cluster to securely write to Cloud
SQL using the Cloud SQL Auth Proxy sidecar container.

### 3. Cost-Optimized Spot VM Node Pools

Deploying stateless frontend pods on GKE Spot VMs to drastically reduce compute
costs, configuring fallback pools with standard VMs.

## Infrastructure Code (Terraform)

### GKE Ingress with Google-Managed Certificate

```terraform
# Define GKE cluster (VPC-Native)
resource "google_container_cluster" "web_cluster" {
  name     = "web-app-cluster"
  location = "us-central1"

  # Enable VPC-native traffic routing (required for Private IPs/NEGs)
  ip_allocation_policy {}
}

# Managed SSL certificate for Ingress
resource "google_compute_managed_ssl_certificate" "default" {
  name = "web-app-ssl-cert"

  managed {
    domains = ["webapp.example.com"]
  }
}
```

### Pod Spec with Cloud SQL Auth Proxy Sidecar

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ecommerce-api
spec:
  replicas: 3
  template:
    metadata:
      labels:
        app: ecommerce-api
    spec:
      containers:
      - name: api-app
        image: gcr.io/my-project/ecommerce-api:latest
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          value: "127.0.0.1"
      # Cloud SQL Auth Proxy Sidecar
      - name: cloud-sql-proxy
        image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.1.0
        args:
          - "--structured-logs"
          - "--port=5432"
          - "my-project:us-central1:my-database"
        securityContext:
          runAsNonRoot: true
```

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Google Kubernetes Engine in Private Data \
description: Describes how GKE is configured for Private Data. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, private_data, "product:gke"]

--------------------------------------------------------------------------------

# Google Kubernetes Engine (GKE) in Private Data

**Usage:** GKE Private Clusters serve as the primary compute environment for
backend microservices handling sensitive data.

**Best Practices:**

-   Configure nodes with only internal IP addresses.
-   Use a private endpoint for the control plane, controlled via Authorized
    Networks.
-   Use VPC-native clusters (Alias IPs) for efficient IP management.
-   Use Workload Identity Federation to securely manage pod identities.
-   Establish strict Kubernetes Network Policies for pod-to-pod segmentation.
