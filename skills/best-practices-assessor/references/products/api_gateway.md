---
type: PerProductBestPractice  
title: API Gateway in Web Applications  
description: Describes how API Gateway is configured to front serverless backend APIs in Web Applications.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, web_applications, "product:api_gateway"]

---

# API Gateway in Web Applications

Describes how API Gateway is configured to front serverless backend APIs in Web
Applications.

## Integration Details

In Web Applications, API Gateway acts as the secure ingress management layer for
serverless backends (like Cloud Functions or Cloud Run APIs). It enforces
authorization (e.g. Firebase Auth JWT verification), API key validation, and
rate limits, before routing paths to specific serverless backends using OpenAPI
specs.

## Target Configurations

### Serverless BFF API Gateway

Setting up an API Gateway using an OpenAPI spec to route endpoints to
specialized Backend-for-Frontend (BFF) Cloud Functions.

## Infrastructure Code (Terraform)

### API Gateway Routing to Cloud Functions

```terraform
resource "google_api_gateway_api" "api" {
  provider = google-beta
  api_id   = "my-web-api"
}

resource "google_api_gateway_api_config" "api_cfg" {
  provider      = google-beta
  api           = google_api_gateway_api.api.api_id
  api_config_id = "cfg-v1"

  openapi_documents {
    document {
      path     = "openapi.yaml"
      contents = base64encode(<<-EOF
        swagger: '2.0'
        info:
          title: My Web API Gateway
          version: 1.0.0
        paths:
          /contact:
            post:
              summary: Submit Contact Form
              operationId: submitContact
              x-google-backend:
                address: https://us-central1-my-project.cloudfunctions.net/contact-form-handler
              responses:
                '200':
                  description: OK
      EOF
      )
    }
  }
}

resource "google_api_gateway_gateway" "gw" {
  provider   = google-beta
  gateway_id = "my-gateway"
  api_config = google_api_gateway_api_config.api_cfg.id
  region     = "us-central1"
}
```
