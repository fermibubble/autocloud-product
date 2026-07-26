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
title: Cloud Spanner in Web Applications \
description: Describes how Cloud Spanner is integrated for globally distributed,
strongly consistent Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_spanner"]

--------------------------------------------------------------------------------

# Cloud Spanner in Web Applications

Describes how Cloud Spanner is integrated for globally distributed, strongly
consistent Web Applications.

## Integration Details

For globally distributed Web Applications, Cloud Spanner serves as a highly
available, multi-region SQL database that guarantees absolute transactional
integrity (ACID) and strong consistency across regions. Spanner is best paired
with multi-regional deployments of Cloud Run or GKE fronted by a Global External
Application Load Balancer.

## Target Configurations

### Multi-Regional Cloud Run to Multi-Region Spanner

Deploying Cloud Run in regional endpoints (e.g., `us-east1`, `europe-west1`) and
accessing a multi-region Cloud Spanner instance via Direct VPC Egress for
low-latency database transactions.

## Infrastructure Code (Terraform)

### Multi-Region Spanner Instance and Database

```terraform
resource "google_spanner_instance" "spanner_inst" {
  config       = "nam-eur-asia1" # Multi-regional configuration (US, Europe, Asia)
  display_name = "Global Web App DB"
  name         = "global-web-db"
  num_nodes    = 1
  edition      = "ENTERPRISE_PLUS"
}

resource "google_spanner_database" "database" {
  instance = google_spanner_instance.spanner_inst.name
  name     = "app_db"
  ddl = [
    "CREATE TABLE Users ( UserId STRING(36) NOT NULL, Email STRING(255), Name STRING(255) ) PRIMARY KEY (UserId)",
    "CREATE TABLE Orders ( UserId STRING(36) NOT NULL, OrderId STRING(36) NOT NULL, OrderDate TIMESTAMP, TotalAmount NUMERIC ) PRIMARY KEY (UserId, OrderId), INTERLEAVE IN PARENT Users ON DELETE CASCADE"
  ]
}
```
