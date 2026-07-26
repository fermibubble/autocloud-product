---
type: ArchetypeBestPractice  
title: Dataflow in Data Processing  
description: Configuring serverless Cloud Dataflow pipelines with Streaming Engine, autoscaling worker pools, and side-output Dead-Letter Queues.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, data_processing, "product:dataflow"]

---

# Dataflow in Data Processing

Describes how Cloud Dataflow is integrated and configured to execute serverless,
parallel data transformation pipelines.

## Integration Details

In Data Processing, Cloud Dataflow is the primary workhorse for running
cloud-native batch and streaming pipelines. Using Apache Beam, it unifies batch
and streaming codebases, ingesting from sources like Pub/Sub and GCS, performing
complex transformations (joining, cleaning, windowing), and writing results to
destinations like BigQuery or Bigtable.

## Target Configurations

### 1. Enable Streaming Engine

For streaming pipelines, always configure the **Streaming Engine** backend
rather than executing shuffle and state operations locally on worker VMs. This
reduces worker VM resource utilization (leading to cheaper worker machine types)
and enables faster, more responsive autoscaling.

### 2. Error Handling & In-Pipeline DLQ

Never let parsing or transient API exceptions crash a streaming pipeline. Use
Apache Beam's **side outputs** to catch processing failures inside the
processing steps (`DoFn`) and redirect them to a separate `PCollection` (the
DLQ), which is written directly to a Pub/Sub dead-letter topic for isolation and
analysis.

## Infrastructure Code (Terraform)

### Streaming Dataflow Flex Template Job

```terraform
resource "google_dataflow_flex_template_job" "pubsub_to_bigquery" {
  provider                = google-beta
  name                    = "realtime-event-ingest"
  container_spec_gcs_path = "gs://dataflow-templates-us-central1/latest/Flex/PubSub_to_BigQuery"

  parameters = {
    inputSubscription = "projects/your-gcp-project-id/subscriptions/realtime-events-sub"
    outputTableSpec   = "your-gcp-project-id:analytics_warehouse.user_events"
  }

  # Worker service account configuration adhering to PoLP
  service_account_email = "dataflow-worker-sa@your-gcp-project-id.iam.gserviceaccount.com"

  # Optional region setup
  region = "us-central1"
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Dataproc in Data Processing \
description: Configuring ephemeral Dataproc clusters, lifecycle policies, and
serverless Spark execution for open-source lift-and-shift batch workloads. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, data_processing, "product:dataproc"]

--------------------------------------------------------------------------------

# Dataproc in Data Processing

Describes how Cloud Dataproc is integrated and configured to execute Spark,
Hadoop, and Hive data processing workloads.

## Integration Details

In Data Processing, Dataproc provides the execution environment for running
open-source big data tools. It is the preferred choice for migrating existing
on-premises or other-cloud Hadoop/Spark pipelines. It uses GCS as a persistent
file system layer, decoupling compute from storage.

## Target Configurations

### 1. Ephemeral Cluster Lifecycle

Do not keep Dataproc clusters active indefinitely for scheduled batch jobs.
Instead, design jobs to run on ephemeral clusters that spin up on-demand, run
the job, and terminate immediately upon completion.

*   Configure the **Lifecycle Config** in Terraform or use **Dataproc Workflow
    Templates** to automatically delete idle clusters after a set time limit
    (e.g. 30 minutes of inactivity).

### 2. Ephemeral Storage (GCS as HDFS replacement)

Configure Spark applications to read from and write to GCS using `gs://` paths.
This leverages the pre-installed GCS connector, allowing you to completely
bypass local HDFS storage and maintain stateless compute nodes.

## Infrastructure Code (Terraform)

### Ephemeral Spark Cluster with Idle Auto-Delete

```terraform
resource "google_dataproc_cluster" "ephemeral_spark_cluster" {
  name   = "ephemeral-spark-cluster"
  region = "us-central1"

  cluster_config {
    # Keep master and worker configurations lightweight
    master_config {
      num_instances = 1
      machine_type  = "n2-standard-4"
    }

    worker_config {
      num_instances = 2
      machine_type  = "n2-standard-4"
    }

    # Automatically clean up resources when cluster is idle
    lifecycle_config {
      idle_delete_ttl = "1800s" # Delete cluster if idle for 30 minutes
    }

    # Custom service account following PoLP
    gce_cluster_config {
      service_account = "dataproc-worker-sa@your-gcp-project-id.iam.gserviceaccount.com"

      # Restrict public IP addresses on cluster VMs
      internal_ip_only = true
    }
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: GCS in Data Processing \
description: GCS configurations, hardware choices, and networking options for
running high-performance data processing pipelines. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, data_processing, "product:gcs_storage"]

--------------------------------------------------------------------------------

# GCS in Data Processing

Describes how Google Cloud Storage (GCS) is integrated and configured for
running data processing pipelines.

## Integration Details

In Data Processing, GCS serves as the primary data lake landing zone, decoupling
compute and storage. Big data engines (Dataproc, Dataflow) read raw data
directly from regional or multi-regional GCS buckets.

## Target Configurations

### 1. Web Applications (User-Generated Content & Static Assets)

*   **Pattern:** Separate static asset serving from dynamic processing. Use GCS
    Backend Buckets behind an External Application Load Balancer to serve static
    assets (images, CSS, JS) via Cloud CDN.
*   **User-Generated Content (UGC):** For dynamic uploads, avoid routing large
    payloads through the compute layer (e.g., Cloud Run). Instead, generate
    short-lived **Signed URLs** from the backend, allowing clients to
    upload/download files directly and securely to/from a private GCS bucket.

### 2. Data Processing & Data Lakes

*   **Pattern:** Decouple compute and storage by landing raw data in a regional
    or multi-regional GCS bucket.
*   **Analytics Integration:** Run big data engines (Dataproc, Dataflow)
    directly against GCS objects. Use BigQuery **BigLake** external tables to
    run analytical queries directly over GCS-hosted parquet or avro files while
    maintaining row- and column-level security.

### 3. AI/ML Workflows

*   **Pattern:** Use GCS as the central repository for raw datasets, training
    logs, checkpoints, and exported model artifacts.
*   **Vertex AI Integration:** Mount GCS buckets to Vertex AI training jobs or
    GKE pods using **Cloud Storage FUSE** to interact with files using standard
    POSIX file system APIs.

### 4. Event-Driven Automation

*   **Pattern:** Trigger serverless functions in response to file lifecycle
    changes.
*   **Flow:** Enable Object Lifecycle notifications to publish messages to a
    Pub/Sub topic, which triggers a Cloud Run service or Cloud Function via
    Eventarc upon object creation (`OBJECT_FINALIZE`) or deletion
    (`OBJECT_DELETE`).

## Infrastructure Code (Terraform)

### Basic Private Bucket with Lifecycle and Versioning

```terraform
resource "google_storage_bucket" "secure_bucket" {
  project       = "your-gcp-project-id"
  name          = "your-unique-bucket-name"
  location      = "us-central1"
  storage_class = "STANDARD"

  # Enforce security best practices
  public_access_prevention = "enforced"
  bucket_policy_only       = true # Uniform bucket-level access

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 604800 # 7 days retention
  }

  # Transition and deletion rules
  lifecycle_rule {
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
    condition {
      age = 30 # Transition to Nearline after 30 days
    }
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 365 # Delete after 1 year
    }
  }
}
```

### Granting IAM Access to Service Account

```terraform
resource "google_storage_bucket_iam_member" "sa_reader" {
  bucket = google_storage_bucket.secure_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:my-app-sa@your-gcp-project-id.iam.gserviceaccount.com"
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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

type: ArchetypeBestPractice \
title: Pub/Sub in Data Processing \
description: Configuring Pub/Sub topics, competing consumer subscriptions, and
dead-letter topics for high-throughput streaming event ingestion. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, data_processing, "product:pubsub"]

--------------------------------------------------------------------------------

# Pub/Sub in Data Processing

Describes how Cloud Pub/Sub is integrated and configured to ingest, buffer, and
route real-time streaming data.

## Integration Details

In Data Processing, Pub/Sub is the ingestion entrypoint for all streaming
pipelines. It acts as a highly durable, global buffer between message producers
(IoT devices, log agents, clickstream trackers) and consumers (Cloud Dataflow,
Cloud Functions, Cloud Run). This buffer levels the load from bursty traffic
spikes, ensuring down-stream workers are not overwhelmed.

## Target Configurations

### 1. Competing Consumers & Load Leveling

*   Configure a single **Pub/Sub Subscription** (Pull or Push) that is consumed
    by multiple parallel instances of a processing service (e.g., Dataflow
    worker pool).
*   Pub/Sub handles load balancing by delivering each message to only one worker
    at a time. Compute runtimes can autoscale based on the subscription's
    **backlog** metrics (unacknowledged messages).

### 2. Dead-Letter Policy (Subscription Level)

*   For serverless event handlers (Cloud Run, Cloud Functions), configure a
    **Dead-Letter Policy** directly on the Pub/Sub subscription.
*   If a message fails to be acknowledged after a specified number of delivery
    attempts (e.g., 5 attempts), Pub/Sub automatically forwards it to a
    designated dead-letter topic for manual inspection and isolation.

## Infrastructure Code (Terraform)

### Pub/Sub Topic and Subscription with Dead-Lettering

```terraform
resource "google_pubsub_topic" "incoming_events" {
  name = "incoming-events"
}

resource "google_pubsub_topic" "events_dead_letter" {
  name = "incoming-events-dlq"
}

resource "google_pubsub_subscription" "events_subscription" {
  name  = "incoming-events-sub"
  topic = google_pubsub_topic.incoming_events.name

  # Enable dead-letter forwarding
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.events_dead_letter.id
    max_delivery_attempts = 5
  }

  # Message retention settings
  message_retention_duration = "604800s" # Retain unacknowledged messages for 7 days
  retain_acked_messages      = false
}
```
