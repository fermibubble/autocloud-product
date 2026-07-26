---
type: ArchetypeBestPractice  
title: Vertex AI Agent Engine in Agent Cloud  
description: Vertex AI Agent Engine configurations and modules optimized for Agent Cloud deployments.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, agent_cloud, "product:agent_engine"]

---

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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Agent Gateway in Agent Cloud \
description: Configuring ingress/egress, authorization policies, and Model Armor
safety filters for Agent Cloud workloads. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, agent_cloud, "product:agent_gateway"]

--------------------------------------------------------------------------------

# Agent Gateway in Agent Cloud

Describes how the Agent Gateway is used to manage ingress and egress boundaries
in Agent Cloud.

## Integration Details

In Agent Cloud, Egress Gateways are set up as `AGENT_TO_ANYWHERE` with
`REQUEST_AUTHZ` policies to block unauthorized exfiltration. Ingress Gateways
are set up as `CLIENT_TO_AGENT` with `CONTENT_AUTHZ` policies to feed inputs
through Model Armor authz extensions.

## Target Configurations

### 1. Data Exfiltration Prevention (Locked Egress)

*   **Pattern:** Sandbox agent runtimes to block arbitrary internet access.
*   **Flow:** The Egress Agent Gateway blocks all outgoing IP/DNS traffic by
    default. Explicit network rule definitions authorize only a strict list of
    Google APIs (like `logging.googleapis.com` or `storage.googleapis.com`) or
    registered MCP server endpoints.

### 2. Inline Prompt Sanitization & Jailbreak Filtering

*   **Pattern:** Transparently filter input prompts at the network boundary
    rather than application code.
*   **Flow:** Inbound traffic passing through the Ingress Agent Gateway is
    inspected. A `CONTENT_AUTHZ` policy routes the payload to a Network Security
    Authz Extension. The extension passes the prompt to a Model Armor template,
    blocking jailbreaks, PII leaks, or toxic content before the prompt reaches
    the Agent Engine.

## Infrastructure Code (Terraform)

### Agent Gateway, Authz Policy, and Model Armor Configuration

This example demonstrates setting up an egress gateway with domain restrictions
and an ingress gateway with Model Armor protection.

```terraform
# 1. Egress Gateway (Locked Outbound Egress)
module "egress_gateway" {
  source                              = "github.com/GoogleCloudPlatform/terraform-google-agent-gateway?ref=v0.4.2"
  project_id                          = var.project_id
  location                            = "us-central1"
  gateway_name                        = "agent-egress-gateway"
  google_managed_governed_access_path = "AGENT_TO_ANYWHERE"
}

# 2. Ingress Gateway (Client-to-Agent Ingress)
module "ingress_gateway" {
  source                              = "github.com/GoogleCloudPlatform/terraform-google-agent-gateway?ref=v0.4.2"
  project_id                          = var.project_id
  location                            = "us-central1"
  gateway_name                        = "agent-ingress-gateway"
  google_managed_governed_access_path = "CLIENT_TO_AGENT"
}

# 3. Model Armor Safety Template
module "model_armor_template" {
  source      = "github.com/GoogleCloudPlatform/terraform-google-vertex-ai//modules/model-armor-template?ref=v5.2.0"
  template_id = "agent-armor-template"
  location    = "us-central1"
  project_id  = var.project_id

  rai_filters = {
    dangerous         = "MEDIUM_AND_ABOVE"
    harassment        = "MEDIUM_AND_ABOVE"
    hate_speech       = "MEDIUM_AND_ABOVE"
    sexually_explicit = "MEDIUM_AND_ABOVE"
  }
  pi_and_jailbreak_filter_settings = "MEDIUM_AND_ABOVE"
  metadata_configs = {
    ignore_partial_invocation_failures = false
    log_sanitize_operations            = true
    log_template_operations            = true
  }
}

# 4. Authz Extension linking Gateway to Model Armor
module "authz_extension" {
  source     = "github.com/GoogleCloudPlatform/terraform-google-network-security-authz//modules/authz-extension?ref=v0.5.2"
  project_id = var.project_id
  location   = "us-central1"
  name       = "agent-authz-ext"
  service    = "modelarmor.us-central1.rep.googleapis.com"
  timeout    = "2.0s"

  model_armor_templates = [
    module.model_armor_template.template_id
  ]
}

# 5. CONTENT_AUTHZ Policy for Ingress Gateway
module "authz_policy_content" {
  source     = "github.com/GoogleCloudPlatform/terraform-google-network-security-authz//modules/authz-policy?ref=v0.5.2"
  project_id = var.project_id
  location   = "us-central1"
  name       = "ingress-content-policy"
  action     = "CUSTOM"
  policy_profile = "CONTENT_AUTHZ"

  target = {
    resources = [module.ingress_gateway.agent_gateway_id]
  }
  custom_provider = {
    authz_extension = {
      resources = [module.authz_extension.id]
    }
  }
}

# 6. REQUEST_AUTHZ Policy for Egress Gateway (Domain Allowlist)
module "authz_policy_request" {
  source     = "github.com/GoogleCloudPlatform/terraform-google-network-security-authz//modules/authz-policy?ref=v0.5.2"
  project_id = var.project_id
  location   = "us-central1"
  name       = "egress-request-policy"
  action     = "ALLOW"
  policy_profile = "REQUEST_AUTHZ"

  target = {
    resources = [module.egress_gateway.agent_gateway_id]
  }

  http_rules = [
    {
      to = {
        operations = {
          hosts = [
            { exact = "aiplatform.googleapis.com", ignore_case = false },
            { exact = "logging.googleapis.com", ignore_case = false },
            { exact = "storage.googleapis.com", ignore_case = false }
          ]
        }
      }
    }
  ]
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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
