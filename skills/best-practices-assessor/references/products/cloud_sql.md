---
type: PerProductBestPractice  
title: Private Database and Caching Connectivity  
description: Configure managed databases with Private IPs.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, security, "product:cloud_sql", "product:memorystore", "product:cloud_spanner"]

---

# Private Database and Caching Connectivity

Configure Cloud SQL and Memorystore with Private IPs, and use Private Service
Connect (PSC) or Private Google Access for Cloud Spanner. Compute resources must
connect privately using Direct VPC Egress (recommended for Cloud Run) or
Serverless VPC Access connectors.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud SQL in Web Applications \
description: Describes how Cloud SQL relational database services are integrated
and secured for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_sql"]

--------------------------------------------------------------------------------

# Cloud SQL in Web Applications

Describes how Cloud SQL relational database services are integrated and secured
for Web Applications.

## Integration Details

In Web Applications, Cloud SQL stores structured transaction data (e.g. users,
products, orders). To prevent exposing the database to the internet, it is
configured with a Private IP in a VPC network. Compute clients (like Cloud Run
or GKE) connect privately using Serverless VPC Access, Direct VPC Egress, or the
Cloud SQL Auth Proxy.

## Target Configurations

### 1. Cloud Run Direct VPC Egress to Private Cloud SQL

Configuring a Cloud Run service to connect directly to a private Cloud SQL
instance using Direct VPC Egress.

### 2. GKE Pods Connecting to Private Cloud SQL via Auth Proxy

Using a sidecar container running the Cloud SQL Auth Proxy inside GKE
deployments to securely forward traffic over a private VPC peer.

## Infrastructure Code (Terraform)

### Cloud Run Service with Direct VPC Egress

```terraform
resource "google_cloud_run_v2_service" "app_service" {
  name     = "secure-app"
  location = "us-central1"

  template {
    containers {
      image = "gcr.io/my-project/my-web-app:latest"

      env {
        name  = "DATABASE_URL"
        value = data.google_secret_manager_secret_version.db_url.secret_data # never a plaintext literal
      }
    }

    # Enable Direct VPC Egress
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
title: Cloud SQL in Private Data \
description: Describes how Cloud SQL is configured for Private Data. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, private_data, "product:cloud_sql"]

--------------------------------------------------------------------------------

# Cloud SQL in Private Data

**Usage:** Relational database storage for transactional workloads (e.g., PCI
compliant payment gateways, HIPAA Telemedicine).

**Best Practices:**

-   Must be configured for **Private IP** access, relying on Private Services
    Access (PSA) or Private Service Connect (PSC).
-   Apply **CMEK** encryption at rest via Cloud KMS.
-   Use IAP-secured Cloud SQL Auth Proxy VMs for administrative access instead
    of public bastion hosts.
