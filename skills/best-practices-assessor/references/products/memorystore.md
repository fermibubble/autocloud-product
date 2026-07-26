---
type: PerProductBestPractice  
title: Centralized Cache for Serverless  
description: Use Memorystore for caching in serverless environments.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, performance, "product:memorystore", "product:cloud_run"]

---

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
title: Private Database and Caching Connectivity \
description: Configure managed databases with Private IPs. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:cloud_sql", "product:memorystore",
"product:cloud_spanner"]

--------------------------------------------------------------------------------

# Private Database and Caching Connectivity

Configure Cloud SQL and Memorystore with Private IPs, and use Private Service
Connect (PSC) or Private Google Access for Cloud Spanner. Compute resources must
connect privately using Direct VPC Egress (recommended for Cloud Run) or
Serverless VPC Access connectors.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Memorystore in Web Applications \
description: Describes how Memorystore (Redis) caching is integrated for Web
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:memorystore"]

--------------------------------------------------------------------------------

# Memorystore in Web Applications

Describes how Memorystore (Redis) caching is integrated for Web Applications.

## Integration Details

In Web Applications, Memorystore (Redis) serves as a high-performance session
cache or application cache. It is crucial for deploying Next.js Incremental
Static Regeneration (ISR) on serverless platforms like Cloud Run, ensuring that
cached pages remain consistent across dynamically scaling stateless container
instances.

## Target Configurations

### 1. Cloud Run Next.js ISR Shared Caching

Configuring Memorystore as the centralized cache provider for Next.js ISR
deployed on Cloud Run.

### 2. GKE Cache Cluster via Private Service Access

Provisioning a Memorystore cluster in the GKE cluster's VPC network, providing
low-latency internal cache nodes to web servers.

## Infrastructure Code (Terraform)

### Memorystore Redis Instance with Private IP

```terraform
resource "google_redis_instance" "cache" {
  name           = "app-cache"
  tier           = "BASIC"
  memory_size_gb = 1

  region             = "us-central1"
  authorized_network = "projects/my-project/global/networks/my-vpc"

  # Connect privately
  connect_mode = "PRIVATE_SERVICE_ACCESS"
}
```
