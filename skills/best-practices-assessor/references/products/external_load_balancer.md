---
type: PerProductBestPractice  
title: External Application Load Balancer in Web Applications  
description: Describes how the External Application Load Balancer routes user traffic to web application backends.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, web_applications, "product:external_load_balancer"]

---

# External Application Load Balancer in Web Applications

Describes how the External Application Load Balancer routes user traffic to web
application backends.

## Integration Details

The External HTTP(S) Load Balancer acts as the unified entrance gateway for Web
Applications. It handles SSL termination, custom domain name mapping, and CDN
edge connections. In serverless web architectures, the Load Balancer connects to
Cloud Run or Cloud Functions via a Serverless Network Endpoint Group (NEG).

## Target Configurations

### 1. Global HTTPS Load Balancer with Serverless NEGs for Cloud Run

Routing global traffic to a Cloud Run web application using regional Serverless
NEGs.

### 2. Multi-Region Load Balancing with Automatic Failover

Setting up backend services pointing to Cloud Run NEGs in multiple regions to
achieve high availability.

## Infrastructure Code (Terraform)

### Load Balancer with Serverless NEG for Cloud Run

```terraform
# Serverless NEG pointing to Cloud Run service
resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "serverless-neg"
  network_endpoint_type = "SERVERLESS"
  region                = "us-central1"

  cloud_run {
    service = "public-web-app"
  }
}

# Backend Service linking the NEG
resource "google_compute_backend_service" "web_backend" {
  name                  = "web-backend-service"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }
}

# URL Map to route requests
resource "google_compute_url_map" "url_map" {
  name            = "web-app-url-map"
  default_service = google_compute_backend_service.web_backend.id
}

# Target HTTPS Proxy for SSL termination
resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "https-proxy"
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.default.id]
}

# Global Forwarding Rule
resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name                  = "http-forwarding-rule"
  ip_address            = google_compute_global_address.default.address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.https_proxy.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_address" "default" {
  name = "lb-static-ip"
}

resource "google_compute_managed_ssl_certificate" "default" {
  name = "managed-cert"
  managed {
    domains = ["app.example.com"]
  }
}
```
