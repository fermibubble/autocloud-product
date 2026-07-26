---
type: PerProductBestPractice  
title: Dataproc Cluster Idle Time  
description: Monitor and transition long-lived Dataproc clusters.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, reliability, "product:dataproc"]

---

# Dataproc Cluster Idle Time

Audit Cluster Idle Time by flagging long-lived Dataproc clusters. Track active
compute hours vs. idle hours, and configure infrastructure to transition
workloads to ephemeral workflow templates if idle time exceeds thresholds.

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
