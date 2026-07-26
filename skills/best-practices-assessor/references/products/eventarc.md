---
type: PerProductBestPractice  
title: Pub/Sub Dead-Letter Topics (DLQ)  
description: Configure DLQs for resilience in event-driven architectures.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, reliability, "product:pubsub", "product:eventarc"]

---

# Pub/Sub Dead-Letter Topics (DLQ)

*   **Utilize Dead-Letter Topics (DLQ) for Resilience:** Configure a DLQ on all
    critical Pub/Sub subscriptions to catch messages that fail processing after
    a set number of delivery attempts (between 5 and 100).
*   **DLQ Subscription Retention:** Always ensure a dedicated, active
    subscription exists on the DLQ topic. Otherwise, undeliverable messages sent
    to the DLQ will be discarded immediately. Expiration (default 7 days) only
    applies to unacknowledged messages in an active subscription.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Eventarc in Event-Driven Architectures \
description: Describes how Eventarc is integrated and configured as the central
event router for the Event-Driven archetype. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, event_driven, "product:eventarc"]

--------------------------------------------------------------------------------

# Eventarc in Event-Driven Architectures

Describes how Eventarc is integrated and configured as the central event router
for the Event-Driven archetype.

## Integration Details

Eventarc acts as the primary event bus and router, simplifying the connection
between diverse native Google Cloud sources, SaaS partners, and serverless
targets (Cloud Run, Functions, Workflows). It standardizes all incoming events
to the CNCF CloudEvents standard format and handles delivery, filtering, and
authentication.

## Target Configurations

### 1. Direct Eventing (e.g., Cloud Storage trigger)

Triggering a serverless destination immediately upon changes to a specific
resource, such as when a file is created in a Cloud Storage bucket.

### 2. Audit Log Triggers

Allows routing events from any Google Cloud service that generates Audit Logs by
filtering the generic `google.cloud.audit.log.v1.written` event type by
`serviceName` and `methodName`.

### 3. Identity and Access Management

Every Eventarc trigger requires an associated Service Account that provides the
identity for event delivery.

*   **Permissions:** The service account must hold the `roles/run.invoker` role
    on the target Cloud Run service for successful delivery.

## Infrastructure Code (Terraform)

### Eventarc Trigger for GCS Object Creation Routing to Cloud Run

```terraform
# Target Cloud Run Service
resource "google_cloud_run_v2_service" "event_receiver" {
  name     = "event-receiver"
  location = "us-central1"

  template {
    containers {
      image = "gcr.io/my-project/my-receiver-app:latest"
    }
  }
}

# Service Account for the Eventarc Trigger
resource "google_service_account" "trigger_sa" {
  account_id   = "eventarc-trigger-sa"
  display_name = "Eventarc Trigger Service Account"
}

# Grant the run.invoker role to the Eventarc service account
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  name     = google_cloud_run_v2_service.event_receiver.name
  location = google_cloud_run_v2_service.event_receiver.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.trigger_sa.email}"
}

# Eventarc Trigger filtering for Storage Object finalized events
resource "google_eventarc_trigger" "gcs_trigger" {
  name     = "gcs-object-finalized-trigger"
  location = "us-central1"
  service_account = google_service_account.trigger_sa.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = "my-input-bucket"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.event_receiver.name
      region  = google_cloud_run_v2_service.event_receiver.location
    }
  }
}
```
