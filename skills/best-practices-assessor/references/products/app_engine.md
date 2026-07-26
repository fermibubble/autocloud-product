---
type: PerProductBestPractice  
title: App Engine in Web Applications  
description: Describes how App Engine is integrated and configured for Web Applications.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, web_applications, "product:app_engine"]

---

# App Engine in Web Applications

Describes how App Engine is integrated and configured for Web Applications.

## Integration Details

In Web Applications, App Engine standard environment serves as a serverless
application platform that scales down to zero when idle and rapidly scales up
during traffic surges. It is commonly configured to serve as a user frontend or
BFF.

## Target Configurations

### 1. Standard Web Application Frontend

A standard configuration running Python, Go, Node.js, or Java standard apps.

## Infrastructure Code (Terraform)

### App Engine Standard Application Configuration

```terraform
resource "google_app_engine_application" "app" {
  project     = var.project_id
  location_id = "us-central"
}

resource "google_app_engine_standard_app_version" "web_frontend" {
  version_id = "v1"
  service    = "default"
  runtime    = "nodejs18"

  entrypoint {
    shell = "node server.js"
  }

  deployment {
    zip {
      source_url = "https://storage.googleapis.com/${var.source_bucket}/code.zip"
    }
  }

  env_variables = {
    NODE_ENV = "production"
  }

  automatic_scaling {
    max_concurrent_requests = 80
    min_idle_instances      = 0
    max_idle_instances      = 3
  }
}
```
