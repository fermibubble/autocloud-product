---
type: PerProductBestPractice  
title: Custom Service Accounts and Granular IAM  
description: Provision dedicated service accounts with granular IAM roles.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, security, "product:gke", "product:cloud_run", "product:vertex_ai", "product:dataflow"]

---

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
title: Dataflow and Native Pub/Sub DLQs \
description: Avoid using native Pub/Sub DLQs with Dataflow pipelines. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:dataflow", "product:pubsub"]

--------------------------------------------------------------------------------

# Dataflow and Native Pub/Sub DLQs

*   **Avoid Native Pub/Sub DLQs with Dataflow:** Relying solely on the native
    Pub/Sub Dead-Letter Topic configuration for Dataflow pipelines is an
    anti-pattern. Dataflow's internal caching and message acknowledgement
    behavior can lead to false positives or missed failures.
*   **How to do it the right way (Side Outputs):** Structure your pipeline
    deployments to utilize explicit side outputs for application-level errors
    (e.g., malformed JSON).
    1.  Define two `TupleTag` objects: one for successfully processed records
        and one for failed (dead-letter) records.
    2.  Wrap your processing logic (inside your `ParDo` transform's `DoFn`) in a
        `try-catch` block.
    3.  If processing succeeds, output to the success tag. If an exception
        occurs, catch it and output to the dead-letter tag (optionally including
        error metadata), rather than letting the exception crash the worker and
        cause infinite retry loops.
    4.  Extract the dead-letter `PCollection` and route it to your chosen
        destination (e.g., a Pub/Sub topic or Cloud Storage bucket for later
        reprocessing).

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Pipeline SLIs and Backlog Monitoring \
description: Monitor SLIs and backlog for data pipelines. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:dataflow", "product:dataproc"]

--------------------------------------------------------------------------------

# Pipeline SLIs and Backlog Monitoring

*   **Define Freshness SLIs:** Measure data freshness using pipeline lag
    metrics. For streaming pipelines, monitor the oldest unacknowledged message
    age in Pub/Sub or the system latency in Dataflow.
*   **Define Correctness SLIs:** Track the ratio of failed jobs to total
    submitted jobs or track the percentage of records routed to the Dead-Letter
    Queue (DLQ).
*   **Monitor Backlog as a Scaling Signal:** Leverage Pub/Sub backlog metrics
    (undelivered message count) to scale workers in your infrastructure
    configurations.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Dataflow in Data Processing \
description: Configuring serverless Cloud Dataflow pipelines with Streaming
Engine, autoscaling worker pools, and side-output Dead-Letter Queues. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, data_processing, "product:dataflow"]

--------------------------------------------------------------------------------

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
