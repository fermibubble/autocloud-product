---
type: PerProductBestPractice  
title: BigQuery Materialized Views  
description: Leverage materialized views for high-frequency reporting to accelerate latency and reduce cost.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, cost_optimization, "product:bigquery"]

---

# BigQuery Materialized Views

For high-frequency reporting and BI dashboards, use materialized views to
pre-aggregate results. BigQuery automatically routes matching queries to use
these views, accelerating latency without requiring query changes.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: BigQuery Table Partitioning and Clustering \
description: Implement native table partitioning and clustering to minimize
query scan sizes and cost. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, cost_optimization, "product:bigquery"]

--------------------------------------------------------------------------------

# BigQuery Table Partitioning and Clustering

Always partition large tables (on ingestion time or event timestamp columns) and
cluster them (on columns frequently used in `WHERE` and `GROUP BY` clauses, such
as `tenant_id` or `user_id`). Partitioning is coarse and prunes data at the
partition level; clustering prunes data at the block level. Do not manually
split data into date-suffixed tables (e.g. `events_20250101`). Manual sharding
generates extreme metadata overhead and degrades query execution planning.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: BigQuery in Data Processing \
description: Designing and configuring BigQuery tables for high-throughput batch
loads, streaming ingestion, and partitioned/clustered query performance. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, data_processing, "product:bigquery"]

--------------------------------------------------------------------------------

# BigQuery in Data Processing

Describes how BigQuery is integrated and configured for high-scale analytical
storage, query execution, and database schema optimizations.

## Integration Details

In Data Processing architectures, BigQuery acts as both the central data
warehouse (the storage sink) and the engine for running SQL-based ad-hoc
queries, reporting, and SQL-native machine learning (BQML). Decoupled compute
engines (Dataflow, Dataproc) ingest data from streams (Pub/Sub) or files (GCS)
and write structured outputs into BigQuery.

## Target Configurations

### 1. High-Throughput Ingestion

*   **Streaming Pipelines:** Leverage the **BigQuery Storage Write API**
    (`STORAGE_WRITE_API`) within Dataflow jobs to achieve low-latency stream
    ingestion with exactly-once delivery guarantees.
*   **Batch Pipelines:** Use **BigQuery Load Jobs** (`FILE_LOADS`) for loading
    massive datasets from GCS. This bypasses streaming quotas and is highly
    cost-efficient.

### 2. Table Optimizations for Cost and Performance

*   **Time Partitioning:** Partition large tables by ingestion time or an event
    timestamp column (e.g. `DAY` or `HOUR`). This limits the amount of data
    scanned by queries.
*   **Clustering:** Cluster tables on frequently filtered or aggregated columns
    (e.g. `tenant_id`, `user_id`, or `device_id`) within partitioned tables to
    prune data further.

## Infrastructure Code (Terraform)

### Partitioned and Clustered BigQuery Table

```terraform
resource "google_bigquery_dataset" "analytics_dataset" {
  dataset_id                  = "analytics_warehouse"
  friendly_name               = "Analytics Warehouse"
  description                 = "Primary warehouse for structured data outputs."
  location                    = "us-central1"
  default_table_expiration_ms = 31536000000 # 365 days
}

resource "google_bigquery_table" "partitioned_events" {
  dataset_id = google_bigquery_dataset.analytics_dataset.dataset_id
  table_id   = "user_events"

  time_partitioning {
    type  = "DAY"
    field = "event_time"
  }

  clustering = ["tenant_id", "event_type"]

  schema = <<EOF
[
  {
    "name": "event_time",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "The timestamp of the event, used for partitioning."
  },
  {
    "name": "tenant_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Tenant identifier used for clustering."
  },
  {
    "name": "event_type",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Event type classification."
  },
  {
    "name": "payload",
    "type": "JSON",
    "mode": "NULLABLE",
    "description": "Raw unstructured event properties."
  }
]
EOF
}
```

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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
