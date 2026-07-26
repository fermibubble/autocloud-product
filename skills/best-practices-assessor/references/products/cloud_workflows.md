---
type: PerProductBestPractice  
title: Cloud Workflows in Scheduled and Orchestration  
description: Describes how Cloud Workflows is configured for Scheduled and Orchestration.  
timestamp: 2026-06-20T13:00:00Z  
tags: [archetypes, scheduled_and_orchestration, "product:cloud_workflows"]

---

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

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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
