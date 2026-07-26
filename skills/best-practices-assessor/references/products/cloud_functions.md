---
type: PerProductBestPractice  
title: Cloud Functions in Scheduled and Orchestration  
description: Describes how Cloud Functions is configured for Scheduled and Orchestration.  
timestamp: 2026-06-20T13:00:00Z  
tags: [archetypes, scheduled_and_orchestration, "product:cloud_functions"]

---

# Cloud Functions in Scheduled and Orchestration

Cloud Functions acts as the "Agent" containing discrete business logic. It's a
serverless, pay-per-use environment ideal for single-purpose functions,
lightweight transformations, API calls, and reacting to Pub/Sub events.

## Role and Integration

*   **Invocation:** Invoked securely by Cloud Scheduler, Cloud Workflows (via
    HTTP/S), or Pub/Sub (via push subscriptions).
*   **OIDC Authentication:** Incoming HTTP requests from Scheduler or Workflows
    are authenticated using OIDC tokens verifying the caller's identity (e.g.,
    granting `roles/cloudfunctions.invoker`).

## Best Practices

*   **Design for Idempotency:** Because Cloud Scheduler and Pub/Sub guarantee
    "at least once" delivery, functions *must* be idempotent to handle retries
    safely without causing unintended side effects (duplicate billing, data
    corruption).

## Anti-Patterns

*   **Orchestrating in Cloud Functions:** Implementing multi-step, stateful
    processes in a single function leads to timeouts, manual state management,
    and poor visibility. Refactor control flow to Cloud Workflows.
*   **Lack of Idempotency:** Failing to implement transaction
    tracking/deduplication checks when triggered by retry-capable services like
    Pub/Sub or Scheduler.
*   **Synchronous Chaining:** Function A calling Function B synchronously.

## Reference Architecture

*   **Dynamic Event Notification:** Pub/Sub pushes to multiple Cloud Functions
    concurrently (email sender, webhook caller, logger). Each acts independently
    and idempotently.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Functions in Web Applications \
description: Describes how Cloud Functions are integrated and configured as
serverless backends or event-driven handlers for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_functions"]

--------------------------------------------------------------------------------

# Cloud Functions in Web Applications

Describes how Cloud Functions are integrated and configured as serverless
backends or event-driven handlers for Web Applications.

## Integration Details

In Web Applications, Cloud Functions (specifically HTTP-triggered functions) are
ideal for serverless API endpoints, handling forms, processing webhooks, or
acting as backends for single-page applications. They scale to zero
automatically, providing a cost-optimized, low-maintenance backend.

## Target Configurations

### Private API backend behind API Gateway

Configuring Cloud Functions to only accept requests coming from an API Gateway
service account.
Invoker permissions (`roles/run.invoker`) should only be given to specific
principals or groups.

## Infrastructure Code (Terraform)

### Private API backend behind API Gateway

```terraform
resource "google_storage_bucket" "code_bucket" {
  name     = "cf-source-code-bucket"
  location = "US"
}

resource "google_storage_bucket_object" "archive" {
  name   = "index.zip"
  bucket = google_storage_bucket.code_bucket.name
  source = "./index.zip"
}

resource "google_cloudfunctions2_function" "function" {
  name        = "private-api-backend"
  location    = "us-central1"
  description = "Private API backend"

  build_config {
    runtime     = "nodejs18"
    entry_point = "handleRequest"
    source {
      storage_source {
        bucket = google_storage_bucket.code_bucket.name
        object = google_storage_bucket_object.archive.name
      }
    }
  }

  service_config {
    max_instance_count = 10
    available_memory   = "256M"
    timeout_seconds    = 60
  }
}

# Service Account for the API Gateway
resource "google_service_account" "gateway_sa" {
  account_id   = "api-gateway-sa"
  display_name = "API Gateway Service Account"
}

# Grant the run.invoker role specifically to the API Gateway service account
resource "google_cloud_run_v2_service_iam_member" "api_gateway_invoker" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  name     = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gateway_sa.email}"
}
```
