---
type: ArchetypeBestPractice  
title: Cloud SQL in Private Data  
description: Describes how Cloud SQL is configured for Private Data.  
timestamp: 2026-06-20T13:00:00Z  
tags: [archetypes, private_data, "product:cloud_sql"]

---

# Cloud SQL in Private Data

**Usage:** Relational database storage for transactional workloads (e.g., PCI
compliant payment gateways, HIPAA Telemedicine).

**Best Practices:**

-   Must be configured for **Private IP** access, relying on Private Services
    Access (PSA) or Private Service Connect (PSC).
-   Apply **CMEK** encryption at rest via Cloud KMS.
-   Use IAP-secured Cloud SQL Auth Proxy VMs for administrative access instead
    of public bastion hosts.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: BigQuery in Private Data \
description: Describes how BigQuery is configured for Private Data. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, private_data, "product:bigquery"]

--------------------------------------------------------------------------------

# BigQuery in Private Data

**Usage:** Data warehouse for secure analytics platforms, retaining sensitive
citizen or healthcare data.

**Best Practices:**

-   Access privately using PSC Endpoints or Private Google Access with
    `restricted.googleapis.com`.
-   Protect using VPC SC.
-   Enforce CMEK at the dataset or table level via Organization Policies.
-   Implement fine-grained data access using column-level and row-level
    security.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Storage in Private Data \
description: Describes how Cloud Storage is configured for Private Data. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, private_data, "product:gcs_storage"]

--------------------------------------------------------------------------------

# Cloud Storage in Private Data

**Usage:** Secure object storage for medical documents, raw data lake ingestion,
and audit log centralization.

**Best Practices:**

-   Secure buckets by placing them within a VPC SC perimeter.
-   Access privately via PSC Endpoints or Private Google Access.
-   Mandate CMEK encryption via Organization Policies
    (`constraints/gcp.restrictNonCmekServices`).
-   Use Signed URLs (Valet Key Pattern) for scoped, time-limited direct client
    access to specific documents (e.g., ePHI).
