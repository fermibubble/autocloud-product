---
type: ArchetypeBestPractice  
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

type: ArchetypeBestPractice \
title: Cloud Run in Scheduled and Orchestration \
description: Describes how Cloud Run is configured for Scheduled and
Orchestration. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, scheduled_and_orchestration, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Scheduled and Orchestration

Cloud Run serves as the "Agent" for longer or more complex discrete tasks within
the archetype. It is a serverless platform running custom containerized
applications and is preferred for services needing custom runtimes or longer
execution times (via Cloud Run Jobs).

## Role and Integration

*   **Invocation:** Cloud Workflows, Cloud Scheduler, and Pub/Sub can all
    trigger Cloud Run services. Workflows can invoke Cloud Run endpoints
    securely.
*   **Private Services:** Workflows can resolve and invoke private Cloud Run
    services (ingress set to 'internal traffic only') using Service Directory.

## Best Practices

*   **Idempotency:** Like Cloud Functions, Cloud Run services must be designed
    to be idempotent to handle the "at least once" delivery mechanisms of
    Scheduler and Pub/Sub. Use unique event IDs or transaction checks.
*   **Unified Observability:** Ensure structured JSON logging is used and that
    `traceparent` headers are propagated through Cloud Run to enable end-to-end
    distributed tracing across the scheduled automation system.

## Anti-Patterns

*   **Lack of Idempotency:** Not checking if a task has already been processed
    before mutating state or performing actions.
*   **Synchronous Service Chaining:** Coupling multiple Cloud Run microservices
    via direct synchronous HTTP calls instead of using Pub/Sub for choreography
    or Workflows for orchestration.

## Reference Architecture

*   **Scheduler-Agent-Supervisor:** Cloud Run acts as the Report Agent,
    generating a long-running report. It updates its state in Firestore. A
    Supervisor workflow monitors Firestore for stalled agents and re-triggers
    them if necessary.

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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

type: ArchetypeBestPractice \
title: Cloud Workflows in Scheduled and Orchestration \
description: Describes how Cloud Workflows is configured for Scheduled and
Orchestration. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, scheduled_and_orchestration, "product:cloud_workflows"]

--------------------------------------------------------------------------------

# Cloud Workflows in Scheduled and Orchestration

Cloud Workflows is the centralized serverless orchestration service that defines
and executes multi-step processes using declarative syntax. It manages complex
flow control (sequential, parallel, conditional logic) and state.

## Role and Integration

*   **State Persistence:** Workflows are stateful and durable, capable of
    pausing, retrying, or waiting up to a year. Internal variables have a 512 KB
    limit.
*   **Error Recovery:** Provides robust error handling (`try/except`), essential
    for the **Saga pattern** and compensating transactions.
*   **Connectivity:** Can securely invoke Cloud Functions, Cloud Run, private
    endpoints (via Service Directory), and dozens of GCP services using native
    Connectors (e.g., BigQuery, Cloud Build, Firestore).

## Best Practices

*   **Prioritize for Complexity:** Use Workflows for multi-step processes with
    conditional logic, long-running steps, or rollback/compensation logic to
    separate flow control from business logic.
*   **Implement Compensating Transactions (Saga):** Explicitly define
    compensating steps for distributed transactions to maintain eventual
    consistency on failure.
*   **Externalize Long-Term State:** Persist task IDs or payload data exceeding
    512 KB to Firestore or Cloud SQL (via an intermediary compute).
*   **Use Callbacks for Human-in-the-Loop:** Use
    `events.create_callback_endpoint` to pause workflows indefinitely for
    external events like human approvals without consuming active execution
    time.

## Anti-Patterns

*   **Orchestrating in Cloud Functions:** Moving complex control flow logic into
    Cloud Functions leads to poor visibility and difficult error recovery.
*   **Hard-coding Endpoints:** Embedding literal URLs for services. Instead, use
    connectors, environment variables, or Service Directory.
*   **Synchronous Chaining of Microservices:** Chaining HTTP calls between
    functions creates brittle dependencies. Use Workflows for stateful
    orchestration instead.

## Reference Architecture

*   **ETL Pipeline Orchestration:** Cloud Scheduler $\rightarrow$ Workflows
    $\rightarrow$ BigQuery connector. Workflows manages long-running query
    execution state and error recovery.
*   **E-commerce Order Fulfillment Saga:** Workflows orchestrates inventory,
    payment, and shipping. If one step fails, Workflows triggers compensating
    subworkflows for previously successful steps.
