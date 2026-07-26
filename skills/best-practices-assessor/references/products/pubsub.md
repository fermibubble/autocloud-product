---
type: PerProductBestPractice  
title: Dataflow and Native Pub/Sub DLQs  
description: Avoid using native Pub/Sub DLQs with Dataflow pipelines.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, reliability, "product:dataflow", "product:pubsub"]

---

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
title: Pub/Sub Dead-Letter Topics (DLQ) \
description: Configure DLQs for resilience in event-driven architectures. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:pubsub", "product:eventarc"]

--------------------------------------------------------------------------------

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
title: Pub/Sub Topic Filtering vs Cost \
description: Balance topic filtering and cost in Pub/Sub designs. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:pubsub"]

--------------------------------------------------------------------------------

# Pub/Sub Topic Filtering vs Cost

Subscription filters perform content-based routing at the Pub/Sub layer.
However, the Pub/Sub cost model charges delivery fees for *every message
evaluated against a subscription*, even if the filter ultimately drops it. For
high-volume streams with sparse interest, use multiple dedicated topics in your
infrastructure rather than subscription filtering.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Pub/Sub in Scheduled and Orchestration \
description: Describes how Pub/Sub is configured for Scheduled and
Orchestration. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, scheduled_and_orchestration, "product:pubsub"]

--------------------------------------------------------------------------------

# Pub/Sub in Scheduled and Orchestration

Pub/Sub provides real-time messaging, acting as the decoupling layer for
choreography scenarios within the Scheduled Automation archetype.

## Role and Integration

*   **Choreography and Fan-out:** Pub/Sub allows a single scheduled event to
    trigger multiple independent services concurrently.
*   **Integration with Scheduler:** Cloud Scheduler can directly publish to a
    Pub/Sub topic, provided the service account has the `Pub/Sub Publisher`
    role.
*   **Integration with Workflows:** Eventarc routes Pub/Sub messages to Cloud
    Workflows using the CloudEvents format, offering standardization and
    built-in DLQ capabilities.
*   **Error Handling:** Features robust retry policies and Dead Letter Topics
    (DLQs) for failed message processing.

## Best Practices

*   **Unified Observability:** Carry the `traceId` through Pub/Sub messages if
    possible or ensure proper log correlation for decoupled components.

## Anti-Patterns

*   **Lack of Idempotency in Subscribers:** Relying on exactly-once delivery.
    Subscribers must handle message redelivery idempotently.

## Reference Architecture

*   **Automated VM Start/Stop:** Cloud Scheduler publishes to a "start" or
    "stop" topic. A subscriber acts on these messages to call the Compute Engine
    API.
*   **Cross-Region Data Synchronization:** A global Pub/Sub topic receives
    scheduled updates, and regional subscriptions push messages to regional
    processors to update local databases, ensuring eventual consistency.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Pub/Sub in Event-Driven Architectures \
description: Describes how Google Cloud Pub/Sub is integrated and configured as
the central transport and message broker for the Event-Driven archetype. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, event_driven, "product:pubsub"]

--------------------------------------------------------------------------------

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

type: PerProductBestPractice \
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

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud Pub/Sub in Microservices \
description: Describes how Cloud Pub/Sub is configured for Microservices. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, microservices, "product:pubsub"]

--------------------------------------------------------------------------------

# Cloud Pub/Sub in Microservices

Cloud Pub/Sub is widely used to decouple microservices and implement
asynchronous communication, which is central to event-driven architectures and
the Saga Choreography pattern.

## Best Practices & Configurations

*   **Asynchronous Communication:** Used as a reliable, highly scalable event
    broker. Cloud Run services often act as consumers via Push Subscriptions
    (webhooks), while GKE/MIGs may use either Push or Pull Subscriptions for
    greater control over message processing rates.
*   **Saga Choreography:** Each service publishes a unique domain event to
    Pub/Sub. Subscribing services act on these events to carry out distributed
    transactions.

## Anti-Patterns

*   **Failing to Implement Idempotency:** Designing event consumers that process
    messages without checking for duplicates. Pub/Sub guarantees at-least-once
    delivery, so non-idempotent processing can lead to data corruption or
    duplicate transactions. Always check a unique transaction ID before
    executing business logic.

## Reference Architectures

*   **Order Processing Saga Choreography:** Cloud Run and GKE Deployment
    utilizing Cloud Pub/Sub as an event-driven bus with idempotent
    subscriptions.
*   **Real-Time Fraud Detection Pipeline:** Cloud Run publisher sending events
    to Pub/Sub, which are pulled by a GKE subscriber.
