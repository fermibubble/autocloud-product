---
type: PerProductBestPractice  
title: Dynamic Attribute-Based Access Control (ABAC)  
description: Apply IAP policies using Common Expression Language (CEL) on Agent Gateways.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, security, "product:agent_gateway", "product:agent_registry"]

---

# Dynamic Attribute-Based Access Control (ABAC)

Apply IAP policies using Common Expression Language (CEL) on Agent Gateways.
This allows policies to evaluate metadata attributes from the Agent Registry in
real time to authorize tool execution.

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
title: Agent Registry in Agent Cloud \
description: Discovering, registering, and securing agents, MCP servers, and
tool endpoints in Agent Cloud. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, agent_cloud, "product:agent_registry"]

--------------------------------------------------------------------------------

# Agent Registry in Agent Cloud

Describes how the Agent Registry is used to register and secure tool endpoints
in Agent Cloud.

## Integration Details

In Agent Cloud, the Agent Registry acts as the service directory. Instead of
hardcoding tool locations in the agent, the agent queries the registry
dynamically. The registry handles logical-to-physical URI translation and
manages tool-level authentication.

## Target Configurations

### 1. Dynamic Tool Discovery

*   **Pattern:** Decouple tool endpoints from agent logic using dynamic
    discovery.
*   **Flow:** When an agent needs to perform an action, instead of querying a
    hardcoded API, it queries the Agent Registry. The registry resolves the
    target MCP server endpoint and verifies that the calling agent's
    cryptographic identity is authorized.

### 2. Zero-Trust Tool Execution via IAP

*   **Pattern:** Use Identity-Aware Proxy to secure tool invocation.
*   **Flow:** The registry configures an MCP server with IAP protection. The
    agent must obtain an OIDC token matching its SPIFFE identity and pass it via
    the IAP gateway. An IAM policy on the registry binding permits only specific
    agents to invoke the tool.

## Infrastructure Code (Terraform)

### Agent Registry and MCP Server Binding Configuration

This example shows how to register an MCP tool service (e.g. BigQuery MCP) and
bind it to an Agent Engine's effective identity.

```terraform
# Register the logical tool service in the registry
module "agent_registry_service" {
  source       = "github.com/GoogleCloudPlatform/terraform-google-agent-registry//modules/agent-registry-service?ref=v0.3.1"
  project_id   = var.project_id
  location     = "us-central1"
  service_id   = "bigquery-mcp-service"
  display_name = "BigQuery MCP Tool Service"

  interfaces = [
    {
      protocol_binding = "JSONRPC"
      url              = "https://bigquery.us-central1.rep.googleapis.com/mcp"
    }
  ]
  mcp_server_spec = {
    content = "{\"tools\": []}"
    type    = "TOOL_SPEC"
  }
}

# Define the physical MCP Server link
module "agent_registry_mcp_server" {
  source     = "github.com/GoogleCloudPlatform/terraform-google-agent-registry//modules/agent-registry-mcp-server?ref=v0.3.1"
  project_id = var.project_id
  location   = "us-central1"
  filter     = module.agent_registry_service.discovery_filter

  module_depends_on = [
    module.agent_registry_service.id
  ]
}

# Bind the authorized Agent Engine identity to the tool via IAP
module "iap_mcp_binding" {
  source        = "github.com/GoogleCloudPlatform/terraform-google-iap-policy//modules/iap-agent-registry-mcp-server-iam-binding?ref=v0.1.1"
  project_id    = var.project_id
  location      = "us-central1"
  mcp_server_id = module.agent_registry_mcp_server.mcp_server_id
  role          = "roles/iap.httpsResourceAccessor"

  agent_engine_effective_ids = [
    var.agent_engine_effective_identity, # SPIFFE ID of the calling agent
  ]
}
```
