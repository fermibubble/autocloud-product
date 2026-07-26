---
type: PerProductBestPractice  
title: Early Prompt Filtering  
description: Set up a Client-to-Agent Ingress Agent Gateway with a Model Armor extension.  
timestamp: 2026-06-25T14:25:24Z  
tags: [best_practices, security, "product:agent_gateway", "product:model_armor"]

---

# Early Prompt Filtering

Set up a Client-to-Agent Ingress Agent Gateway with a Model Armor extension.
Filtering out prompt injections before they reach the LLM compute layer
preserves resources and mitigates exploits.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Dynamic Attribute-Based Access Control (ABAC) \
description: Apply IAP policies using Common Expression Language (CEL) on Agent
Gateways. \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:agent_gateway",
"product:agent_registry"]

--------------------------------------------------------------------------------

# Dynamic Attribute-Based Access Control (ABAC)

Apply IAP policies using Common Expression Language (CEL) on Agent Gateways.
This allows policies to evaluate metadata attributes from the Agent Registry in
real time to authorize tool execution.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Default-Block Egress Gateway \
description: Configure the Egress Agent Gateway in Enforced mode
(Default-Block). \
timestamp: 2026-06-25T14:25:24Z \
tags: [best_practices, security, "product:agent_gateway"]

--------------------------------------------------------------------------------

# Default-Block Egress Gateway

Configure the Egress Agent Gateway in Enforced mode (Default-Block). All
outbound traffic must be explicitly allowed via IAM policies/rules tied directly
to registered attributes.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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
