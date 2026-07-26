---
type: PerProductBestPractice  
title: Cloud Storage FUSE Caching  
description: Accelerate model weight loading using GCS FUSE Anywhere Cache.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, performance, "product:gcs_storage", "product:gke"]

---

# Cloud Storage FUSE Caching

Mount Cloud Storage buckets as local file systems on worker nodes for fast,
parallel model weight downloading. Configure and enable **Anywhere Cache** to
speed up cold starts for AI/ML workloads.

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
title: Customer-Managed Encryption Keys (CMEK) \
description: Enable CMEK using Cloud KMS for sensitive data. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:gcs_storage"]

--------------------------------------------------------------------------------

# Customer-Managed Encryption Keys (CMEK)

Enable CMEK using Cloud KMS for all persistent storage buckets, operational
tables, and vector indexes containing sensitive training data.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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

type: PerProductBestPractice \
title: Cloud Storage in Web Applications \
description: Describes how Google Cloud Storage (GCS) is configured to host
static sites or serve static assets for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:gcs_storage"]

--------------------------------------------------------------------------------

# Cloud Storage in Web Applications

Describes how Google Cloud Storage (GCS) is configured to host static sites or
serve static assets for Web Applications.

## Integration Details

In Web Applications, GCS is widely used as a serverless origin for hosting
Single-Page Applications (SPAs) or static marketing websites (SSG). By placing
an External Application Load Balancer and Cloud CDN in front of a GCS bucket,
you obtain a fast, secure, globally distributed static hosting solution.

## Target Configurations

### 1. Public Static Web Bucket

Configuring a bucket to serve static HTML (indexing `index.html` and `404.html`)
directly.

### 2. Backend Bucket behind Load Balancer & CDN

Keeping the bucket private or public, but routing all client requests through an
HTTP(S) Load Balancer backend bucket with Cloud CDN enabled to cache pages at
Google edge nodes.

## Infrastructure Code (Terraform)

### Public Static Web Bucket Setup

```terraform
resource "google_storage_bucket" "static_website" {
  name          = "static-marketing-website-bucket"
  location      = "US"
  force_destroy = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }
}

# Grant public read access to all objects in the bucket
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.static_website.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
```

### Private Bucket as Load Balancer Backend Bucket with CDN

```terraform
resource "google_storage_bucket" "private_assets" {
  name     = "private-webapp-assets"
  location = "US"
}

# Configure Backend Bucket for Load Balancer
resource "google_compute_backend_bucket" "cdn_backend" {
  name        = "assets-backend-bucket"
  bucket_name = google_storage_bucket.private_assets.name
  enable_cdn  = true
}
```

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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
