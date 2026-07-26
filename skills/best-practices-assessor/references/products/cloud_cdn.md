---
type: PerProductBestPractice  
title: Cloud CDN for Static Content  
description: Deliver static content efficiently using Cloud CDN.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, performance, "product:cloud_cdn", "product:cloud_run", "product:gke"]

---

# Cloud CDN for Static Content

Front all static storage origins (like GCS buckets hosting SPAs/assets or
Compute Engine instance groups) with Cloud CDN to cache assets close to users.

This solves several issues by accelerating the delivery of web and video content
(such as HTML, CSS, JavaScript, and images). By serving content from edge caches
close to users, Cloud CDN reduces latency, lowers the load on your origin
servers, and decreases network delivery costs. It is recommended to use the
default `CACHE_ALL_STATIC` cache mode to automatically identify and cache common
static content types.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Cloud CDN in Web Applications \
description: Describes how Cloud CDN caching is configured and optimized for Web
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_cdn"]

--------------------------------------------------------------------------------

# Cloud CDN in Web Applications

Describes how Cloud CDN caching is configured and optimized for Web
Applications.

## Integration Details

In Web Applications, Cloud CDN is integrated directly into the External
Application Load Balancer at the backend bucket or backend service level. It
caches static assets (JS, CSS, images) and eligible dynamic responses (using
appropriate Cache-Control headers) at edge points of presence, dramatically
speeding up user request response times and reducing egress bandwidth billing on
origins.

## Target Configurations

### 1. Cloud CDN for Static Storage Buckets

Caching website assets stored in Google Cloud Storage buckets.

### 2. Caching for Dynamic Server Backends (Cloud Run / GKE)

Enabling caching for APIs or SSR frontends by enabling Cloud CDN on the Load
Balancer backend service.

## Infrastructure Code (Terraform)

### Load Balancer Backend Service with Cloud CDN Enabled

```terraform
resource "google_compute_backend_service" "api_backend" {
  name                  = "api-backend-service"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  # Enable Cloud CDN caching
  enable_cdn = true

  cdn_policy {
    cache_mode = "CACHE_ALL_STATIC"
    default_ttl = 3600
    client_ttl  = 3600
    max_ttl     = 86400
  }
}
```
