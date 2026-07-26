---
type: ArchetypeBestPractice  
title: Cloud Pub/Sub in Event-Driven Architectures  
description: Describes how Google Cloud Pub/Sub is integrated and configured as the central transport and message broker for the Event-Driven archetype.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, event_driven, "product:pubsub"]

---

# Cloud Pub/Sub in Event-Driven Architectures

Describes how Google Cloud Pub/Sub is integrated and configured as the central
transport and message broker for the Event-Driven archetype.

## Integration Details

In Event-Driven Architectures, Cloud Pub/Sub serves as the global,
high-throughput messaging backbone. It implements the Publisher-Subscriber
pattern, routing messages from publishers to multiple subscriptions
asynchronously. This decouples producing microservices from consuming services,
enabling independent scaling and evolution.

## Target Configurations

### 1. Push Subscriptions to Serverless Sinks

Push subscriptions are the standard for serverless compute destinations (Cloud
Run/Cloud Functions). Pub/Sub pushes the event payload via an HTTP POST request,
utilizing OIDC token authentication.

### 2. Message Ordering (FIFO)

When message sequence matters (e.g., state-mutating sequences), enabling message
ordering enforces that messages with the same `ordering_key` are processed
sequentially.

*   **Constraint:** Concurrency is limited to one outstanding message per
    ordering key.
*   **Warning:** ACK deadline expiration will trigger redelivery of all
    subsequent messages for that ordering key.

### 3. Dead-Letter Topics (DLQ)

Enabling Dead-Letter Topics redirect poisoned messages that cannot be processed
after a specified number of delivery attempts (between 5 and 100). This prevents
processing pipelines from stalling.

### 4. Subscription Filters

Used for content-based routing, filtering messages based on custom attributes
(e.g., `attributes.eventType = "OrderCreated"`). Only matching messages are
delivered to the subscription, while non-matching messages are auto-acknowledged
by Pub/Sub.

## Infrastructure Code (Terraform)

### Push Subscription with Dead-Letter Topic and Filtering

```terraform
resource "google_pubsub_topic" "event_topic" {
  name = "event-topic"
}

resource "google_pubsub_topic" "dead_letter_topic" {
  name = "dead-letter-topic"
}

resource "google_pubsub_subscription" "filtered_push_sub" {
  name  = "order-created-sub"
  topic = google_pubsub_topic.event_topic.id

  # Push configuration targeting Cloud Run
  push_config {
    push_endpoint = "https://order-processor-xzy.a.run.app/"
    oidc_token {
      service_account_email = "pubsub-invoker@my-project.iam.gserviceaccount.com"
    }
  }

  # Message retention and ack deadline
  ack_deadline_seconds = 60
  message_retention_duration = "604800s" # 7 days

  # Content-based message filtering
  filter = "attributes.eventType = \"OrderCreated\""

  # Dead Letter Policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter_topic.id
    max_delivery_attempts = 5
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Functions for Event-Driven Architectures \
description: Integration details for using Cloud Functions in event-driven
systems. \
timestamp: 2026-06-21T14:58:33Z \
tags: [archetypes, event_driven]

--------------------------------------------------------------------------------

# Cloud Functions in Event-Driven Architectures

Cloud Functions, particularly Gen 2, are deeply integrated with Eventarc and
Pub/Sub, making them a primary compute choice for event-driven systems.

## Architectures

*   **Pub/Sub Triggers:** Functions invoked asynchronously for every message
    published to a specific Pub/Sub topic. Ideal for decoupling microservices or
    asynchronous task processing.
*   **Storage Triggers:** Functions invoked by Cloud Storage events (e.g.,
    `google.cloud.storage.object.v1.finalized`). Used for automated file
    processing, image resizing, or data validation pipelines.
*   **Eventarc Triggers:** Functions triggered by a wider array of Google Cloud
    events using Eventarc. Provides a unified event delivery model for Gen 2
    functions.
*   **Cloud Logging:** Trigger functions in response to specific log entries.
*   **Cloud Scheduler:** Execute functions on a cron-based schedule.
*   **Cloud Tasks:** Execute functions asynchronously with advanced rate
    limiting and retry controls.
*   **Webhooks:** Trigger functions from third-party systems via HTTP endpoints.

## Configuration Specifics

*   **Event Trigger Settings:** Configure the `event_trigger` block in Terraform
    (`google_cloudfunctions2_function`) with the specific `event_type` and
    `pubsub_topic` or other resources.
*   **Retry Policies:** Explicitly configure retry mechanisms for event-driven
    functions to handle transient failures, ensuring events are not lost but
    also preventing infinite retry loops.

## Failure Scenarios

*   **Event Delivery Latency:** While usually immediate, event delivery can
    occasionally experience latency. Functions should be idempotent to handle
    potential duplicate event deliveries.
*   **Dead Letter Queues:** If a function repeatedly fails to process a Pub/Sub
    message, the message may be lost unless Dead Letter Queues (DLQ) are
    configured on the underlying Pub/Sub subscription.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Run in Event-Driven Architectures \
description: Describes how Cloud Run is integrated and configured as an event
consumer (sink) in the Event-Driven archetype. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, event_driven, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Event-Driven Architectures

Describes how Cloud Run is integrated and configured as an event consumer (sink)
in the Event-Driven archetype.

## Integration Details

In Event-Driven Architectures, Cloud Run hosts the stateless business logic that
reacts to events routed by Pub/Sub or Eventarc. It utilizes automated HTTP
endpoints (for push subscriptions) or client libraries (for pull subscriptions)
to process messages. Scale-to-zero compute minimizes idle cost, while rapid
autoscaling handles high-volume traffic bursts.

## Target Configurations

### 1. Push Ingestion (Recommended Baseline)

The default configuration where Pub/Sub or Eventarc delivers events via HTTP
POST requests.

*   **Authentication:** Requires the incoming request to carry a Google-signed
    OIDC JWT, and the routing service's identity must hold the
    `roles/run.invoker` role on the Cloud Run service.

### 2. Ingestion in VPC Service Controls (VPC-SC) Perimeters

When a service is protected within a VPC Service Controls (VPC-SC) perimeter,
push subscriptions to Cloud Run are supported by configuring proper VPC-SC
ingress rules.

*   **Solution:** Configure the VPC-SC perimeter ingress rules to allow the
    Pub/Sub service account to invoke the Cloud Run service, enabling secure
    HTTP push delivery.

### 3. Direct VPC Egress for Database/Cache Access

If the consumer needs to mutate private backend state (e.g., writing clickstream
profile updates to Cloud Memorystore for Redis or Cloud SQL using private IPs),
it must utilize Serverless VPC Access or Direct VPC Egress.

*   **Recommendation:** Direct VPC Egress is preferred for lower latency and
    simpler setup.

### 4. Idempotent Processing

Given Pub/Sub's at-least-once delivery guarantee, Cloud Run services must be
designed for idempotency.

*   **Pattern:** Perform a transactional check against a database (e.g.,
    Firestore) using the event's unique ID to ensure the event has not been
    processed previously.

## Infrastructure Code (Terraform)

### Private Cloud Run Event Consumer with Direct VPC Egress

```terraform
# Service Account for Cloud Run Service
resource "google_service_account" "run_sa" {
  account_id   = "cloud-run-consumer-sa"
  display_name = "Cloud Run Consumer Service Account"
}

# Private Cloud Run Service configured to receive internal traffic only
resource "google_cloud_run_v2_service" "event_consumer" {
  name     = "event-consumer-service"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.run_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 50
    }

    containers {
      image = "gcr.io/my-project/my-consumer-app:latest"
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }

    # Direct VPC Egress for private database connectivity
    vpc_access {
      network_interfaces {
        network    = "projects/my-project/global/networks/my-vpc"
        subnetwork = "projects/my-project/regions/us-central1/subnetworks/my-subnet"
      }
      egress = "ALL_TRAFFIC"
    }
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Workflows in Event-Driven Architectures \
description: Describes how Cloud Workflows is integrated and configured as the
stateful orchestration engine in the Event-Driven archetype. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, event_driven, "product:cloud_workflows"]

--------------------------------------------------------------------------------

# Cloud Workflows in Event-Driven Architectures

Describes how Cloud Workflows is integrated and configured as the stateful
orchestration engine in the Event-Driven archetype.

## Integration Details

In Event-Driven Architectures, Cloud Workflows provides centralized, stateful
coordination for complex multi-step processes (Orchestration Saga pattern).
Unlike pure Choreography, it offers explicit state tracking, retry/compensation
logic, and direct integration with GCP APIs. It can pause execution for up to
one year to wait for asynchronous external signals, making it ideal for
human-in-the-loop approvals.

## Target Configurations

### 1. Event-Driven Workflow Triggering

Triggered by Eventarc, which maps an incoming event (e.g., GCS upload, Pub/Sub
message) to a workflow invocation. Eventarc passes the event payload as a JSON
runtime argument to the workflow.

### 2. Orchestration Saga (Compensation Logic)

Implementing transactions across multiple microservices. If any step fails, the
workflow catches the error and executes compensation steps (rollback actions) to
keep downstream state consistent.

### 3. Human-in-the-Loop Callback (Wait and Resume)

Pausing execution to wait for a manual action.

*   **Mechanism:** Create a callback endpoint via
    `events.create_callback_endpoint` and pause the execution using
    `events.await_callback`. The callback URL is written to an external system
    (e.g., Google Sheets, ticketing system). Once a human approves, an external
    script calls the URL to resume.

## Infrastructure Code (Workflows DSL & Terraform)

### Workflows Definition: Saga with Human Approval

```yaml
main:
  params: [event]
  steps:
    - init:
        assign:
          - order_id: ${event.data.orderId}
          - amount: ${event.data.amount}
    - charge_payment:
        try:
          call: http.post
          args:
            url: https://payment-service-xzy.a.run.app/charge
            body:
              orderId: ${order_id}
              amount: ${amount}
            auth:
              type: OIDC
          result: payment_result
        except:
          as: e
          steps:
            - handle_payment_failure:
                raise: ${e}
    - require_manual_approval:
        steps:
          - create_callback:
              call: events.create_callback_endpoint
              args:
                http_callback_method: "POST"
              result: callback_details
          - publish_approval_task:
              # Simulate publishing task containing callback URL to external DB/system
              call: http.post
              args:
                url: https://admin-dashboard-xzy.a.run.app/tasks
                body:
                  orderId: ${order_id}
                  callbackUrl: ${callback_details.url}
                auth:
                  type: OIDC
          - await_approval:
              call: events.await_callback
              args:
                callback: ${callback_details}
                timeout: 86400 # 24 hours
              result: approval_result
    - ship_order:
        try:
          call: http.post
          args:
            url: https://shipping-service-xzy.a.run.app/ship
            body:
              orderId: ${order_id}
            auth:
              type: OIDC
        except:
          as: e
          steps:
            - refund_payment: # Compensation step
                call: http.post
                args:
                  url: https://payment-service-xzy.a.run.app/refund
                  body:
                    orderId: ${order_id}
                  auth:
                    type: OIDC
            - fail_workflow:
                raise: "Shipping failed, payment refunded."
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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
