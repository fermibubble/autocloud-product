---
type: PerProductBestPractice  
title: Serverless Compute Cost Optimization  
description: Leverage scale-to-zero capabilities in Cloud Run and Agent Engine.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, cost_optimization, "product:cloud_run", "product:agent_engine"]

---

# Serverless Compute Cost Optimization

Leverage Vertex AI Agent Engine (Reasoning Engine) or Cloud Run rather than GKE
for workloads with sporadic, variable, or low-throughput inference patterns.
Both runtimes support scaling down to zero instances, eliminating baseline idle
compute costs.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Agent SPIFFE Identities \
description: Bind SPIFFE IDs to GCP IAM roles. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:agent_engine",
"product:agent_registry"]

--------------------------------------------------------------------------------

# Agent SPIFFE Identities

Always assign agents immutable, cryptographically verifiable Agent Identities.
Bind SPIFFE IDs to GCP IAM roles.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Dynamic Endpoint Resolution \
description: Resolve endpoints dynamically using Agent Registry and App Hub. \
timestamp: 2026-06-20T13:11:30Z \
tags: [best_practices, reliability, "product:agent_engine",
"product:agent_registry"]

--------------------------------------------------------------------------------

# Dynamic Endpoint Resolution

Utilize native Agent Registry capabilities (integrated with App Hub) to resolve
tool and MCP server endpoints dynamically. This avoids static endpoint routes
and enables automatic routing to the nearest active tool instance.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Vertex AI Agent Engine in Agent Cloud \
description: Vertex AI Agent Engine configurations and modules optimized for
Agent Cloud deployments. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, agent_cloud, "product:agent_engine"]

--------------------------------------------------------------------------------

# Vertex AI Agent Engine in Agent Cloud

Describes how Vertex AI Agent Engine is customized and configured for Agent
Cloud deployments.

## Integration Details

In Agent Cloud, the Agent Engine hosts the core agent reasoning code (ADK or
LangChain). It binds cryptographically verifiable SPIFFE Agent Identities to
make passwordless, secure connections to tool endpoints (MCP servers) and govern
ingress/egress boundaries.

## Target Configurations

### 1. Governed Agent Runtime (Base Topology)

*   **Pattern:** Enforce zero-trust boundaries around the agent runtime.
*   **Flow:** The agent code runs in the Agent Engine compute layer. It uses its
    **Agent Identity (SPIFFE)** to authenticate to other GCP services and MCP
    tools. All outbound (egress) tool and API calls are forced through an
    **Egress Agent Gateway** which performs L7 traffic inspection and domain
    allow-listing, while ingress is routed through an **Ingress Agent Gateway**
    to filter prompt injections.

### 2. Multi-Agent Specialization

*   **Pattern:** Distribute complex tasks from a central Root Agent to
    specialized worker agents.
*   **Flow:** Create separate Agent Engine instances for each specialized agent
    (e.g., SQL Agent, Python Exec Agent). Since each instance has a unique
    identity, you can grant them different least-privilege IAM permissions. The
    Root Agent communicates with the workers via RPC.

## Infrastructure Code (Terraform)

### Vertex AI Agent Engine Module Configuration

This example demonstrates configuring a Vertex AI Agent Engine with
`AGENT_IDENTITY` and connecting it to governance gateways.

```terraform
module "agent_engine" {
  source       = "github.com/GoogleCloudPlatform/terraform-google-vertex-ai//modules/agent-engine-nightly?ref=v5.3.2"
  project_id   = var.project_id
  region       = "us-central1"
  display_name = "governed-reasoning-agent"

  spec = {
    agent_framework = "google-adk"
    class_methods = [{
      api_mode    = "async_stream"
      method_name = "async_stream_query"
    }]
    deployment_spec = {
      container_concurrency = 1
      max_instances         = 3
      min_instances         = 1
      env = {
        GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY         = "true"
        OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = "true"
      }
    }
    identity_type = "AGENT_IDENTITY"
    source_code_spec = {
      inline_source = {
        source_archive = "H4sIAAAAAAAAA..." # Compressed source payload
      }
      python_spec = {
        entrypoint_module = "agent"
        entrypoint_object = "root_agent"
        requirements_file = "requirements.txt"
        version           = "3.11"
      }
    }
  }

  # Hook the reasoning engine into the ingress and egress gateways
  google_managed_agent_gateway_config = [
    {
      gateway_id   = module.egress_gateway.agent_gateway_id
      gateway_type = module.egress_gateway.google_managed_gateway_type
    },
    {
      gateway_id   = module.ingress_gateway.agent_gateway_id
      gateway_type = module.ingress_gateway.google_managed_gateway_type
    }
  ]

  # IAM roles configuration
  service_account_roles    = ["roles/networkservices.admin"]
  effective_identity_roles = ["roles/modelarmor.user", "roles/modelarmor.calloutUser"]
}
```
