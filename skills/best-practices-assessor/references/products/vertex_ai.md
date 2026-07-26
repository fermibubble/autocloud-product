---
type: PerProductBestPractice  
title: Endpoint Traffic Splitting  
description: Utilize traffic splitting on Vertex AI endpoints for canary deployments.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, mlops_lifecycle, "product:vertex_ai"]

---

# Endpoint Traffic Splitting

Utilize traffic splitting on Vertex AI endpoints for canary deployments.

## Guidelines

*   **Traffic Splitting:** Utilize traffic splitting on serving endpoints to
    perform safe canary deployments or A/B testing.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Vertex AI Model Monitoring \
description: Connect model monitoring to prediction endpoints to detect drift
and skew. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, mlops_lifecycle, "product:vertex_ai"]

--------------------------------------------------------------------------------

# Vertex AI Model Monitoring

Connect model monitoring to prediction endpoints to detect drift and skew.

## Guidelines

*   **Model Monitoring:** Connect Vertex AI Model Monitoring services to live
    prediction endpoints. Monitor incoming requests in real-time to detect
    training-serving skew and feature drift, which can trigger automated
    retraining pipelines when performance metrics fall below thresholds.

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
title: VPC Service Controls (VPC-SC) \
description: Set up service perimeters for core AI/ML APIs. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:vertex_ai", "product:gcs_storage"]

--------------------------------------------------------------------------------

# VPC Service Controls (VPC-SC)

Always enclose core AI/ML APIs (`aiplatform.googleapis.com`,
`discoveryengine.googleapis.com`, `documentai.googleapis.com`), along with their
dependency storage services (`storage.googleapis.com`,
`bigquery.googleapis.com`), inside a strict VPC Service Controls perimeter. This
prevents unauthorized access to internal training datasets and model parameters,
and blocks egress paths to unapproved external resources.

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
title: Private Service Connect (PSC) Endpoints \
description: Use PSC to expose managed model serving endpoints privately. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:vertex_ai"]

--------------------------------------------------------------------------------

# Private Service Connect (PSC) Endpoints

Use PSC to expose managed model serving endpoints and vector databases (AlloyDB,
Vertex AI Vector Search) privately within your VPC.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Vertex AI in AI/ML Applications \
description: Describes how Vertex AI is customized and configured for AI/ML
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, ai_ml, "product:vertex_ai"]

--------------------------------------------------------------------------------

# Vertex AI in AI/ML Applications

Describes how Vertex AI is customized and configured for AI/ML Applications.

## Integration Details

Vertex AI integrates custom model training pipelines and serving endpoints into
AI/ML topologies. It supports foundation models and pipelines.

## Target Configurations

### 1. MLOps Pipeline for Custom Model Training & Serving

*   **Pattern:** Automate model training and deployment using **Vertex AI
    Pipelines** (based on Kubeflow SDK).
*   **Flow:** LAND new data in GCS or BigQuery, trigger a Vertex AI Pipeline to
    preprocess data, execute a custom containerized training job, evaluate the
    trained model, register the artifact in **Vertex AI Model Registry**, and
    deploy it to a **Vertex AI Endpoint** for online serving. Monitor prediction
    traffic with **Vertex AI Model Monitoring** to detect drift.

### 2. Retrieval-Augmented Generation (RAG)

*   **Pattern:** Ground large language models with private data to reduce
    hallucinations.
*   **Flow:** Process unstructured documents from GCS using Document AI,
    generate vector embeddings using Vertex AI text embedding models (e.g.
    `text-embedding-004`), store vectors in **Vertex AI Vector Search** (or
    `pgvector` in Cloud SQL/AlloyDB), and query the vector store to supply
    context to the LLM during user chats.

### 3. Serverless Inference vs. Endpoint Inference

*   **Trade-off:**
    *   Use **Vertex AI Endpoints** for highly active services needing
        low-latency, dedicated compute (GPU/TPU). It has continuous baseline
        costs.
    *   Use **Cloud Run** (with or without GPU) for sporadic, variable, or
        low-throughput inference workloads that benefit from scaling down to
        zero instances.

## Infrastructure Code (Terraform)

### Vertex AI Endpoint

```terraform
resource "google_vertex_ai_endpoint" "model_endpoint" {
  project      = "your-gcp-project-id"
  name         = "image-classifier-endpoint"
  display_name = "Image Classifier Endpoint"
  location     = "us-central1"
}
```

### Vertex AI Dataset

```terraform
resource "google_vertex_ai_dataset" "custom_dataset" {
  project      = "your-gcp-project-id"
  display_name = "training-dataset"
  metadata_schema_uri = "gs://google-cloud-aiplatform/schema/dataset/metadata/image_1.0.0.yaml"
  region       = "us-central1"
}
```
