---
type: ArchetypeBestPractice  
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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud SQL in Web Applications \
description: Describes how Cloud SQL relational database services are integrated
and secured for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_sql"]

--------------------------------------------------------------------------------

# Cloud SQL in Web Applications

Describes how Cloud SQL relational database services are integrated and secured
for Web Applications.

## Integration Details

In Web Applications, Cloud SQL stores structured transaction data (e.g. users,
products, orders). To prevent exposing the database to the internet, it is
configured with a Private IP in a VPC network. Compute clients (like Cloud Run
or GKE) connect privately using Serverless VPC Access, Direct VPC Egress, or the
Cloud SQL Auth Proxy.

## Target Configurations

### 1. Cloud Run Direct VPC Egress to Private Cloud SQL

Configuring a Cloud Run service to connect directly to a private Cloud SQL
instance using Direct VPC Egress.

### 2. GKE Pods Connecting to Private Cloud SQL via Auth Proxy

Using a sidecar container running the Cloud SQL Auth Proxy inside GKE
deployments to securely forward traffic over a private VPC peer.

## Infrastructure Code (Terraform)

### Cloud Run Service with Direct VPC Egress

```terraform
resource "google_cloud_run_v2_service" "app_service" {
  name     = "secure-app"
  location = "us-central1"

  template {
    containers {
      image = "gcr.io/my-project/my-web-app:latest"

      env {
        name  = "DATABASE_URL"
        value = data.google_secret_manager_secret_version.db_url.secret_data # never a plaintext literal
      }
    }

    # Enable Direct VPC Egress
    vpc_access {
      network_interfaces {
        network    = "projects/my-project/global/networks/my-vpc"
        subnetwork = "projects/my-project/regions/us-central1/subnetworks/my-subnet"
      }
      egress = "ALL_TRAFFIC"
    }
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Functions in Web Applications \
description: Describes how Cloud Functions are integrated and configured as
serverless backends or event-driven handlers for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_functions"]

--------------------------------------------------------------------------------

# Cloud Functions in Web Applications

Describes how Cloud Functions are integrated and configured as serverless
backends or event-driven handlers for Web Applications.

## Integration Details

In Web Applications, Cloud Functions (specifically HTTP-triggered functions) are
ideal for serverless API endpoints, handling forms, processing webhooks, or
acting as backends for single-page applications. They scale to zero
automatically, providing a cost-optimized, low-maintenance backend.

## Target Configurations

### Private API backend behind API Gateway

Configuring Cloud Functions to only accept requests coming from an API Gateway
service account.
Invoker permissions (`roles/run.invoker`) should only be given to specific
principals or groups.

## Infrastructure Code (Terraform)

### Private API backend behind API Gateway

```terraform
resource "google_storage_bucket" "code_bucket" {
  name     = "cf-source-code-bucket"
  location = "US"
}

resource "google_storage_bucket_object" "archive" {
  name   = "index.zip"
  bucket = google_storage_bucket.code_bucket.name
  source = "./index.zip"
}

resource "google_cloudfunctions2_function" "function" {
  name        = "private-api-backend"
  location    = "us-central1"
  description = "Private API backend"

  build_config {
    runtime     = "nodejs18"
    entry_point = "handleRequest"
    source {
      storage_source {
        bucket = google_storage_bucket.code_bucket.name
        object = google_storage_bucket_object.archive.name
      }
    }
  }

  service_config {
    max_instance_count = 10
    available_memory   = "256M"
    timeout_seconds    = 60
  }
}

# Service Account for the API Gateway
resource "google_service_account" "gateway_sa" {
  account_id   = "api-gateway-sa"
  display_name = "API Gateway Service Account"
}

# Grant the run.invoker role specifically to the API Gateway service account
resource "google_cloud_run_v2_service_iam_member" "api_gateway_invoker" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  name     = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gateway_sa.email}"
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Storage in Web Applications \
description: Describes how Google Cloud Storage (GCS) is configured to host
static sites or serve static assets for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:gcs_storage"]

--------------------------------------------------------------------------------

# Cloud Storage in Web Applications

Describes how Google Cloud Storage (GCS) is configured to host static sites or
serve static assets for Web Applications.

## Integration Details

In Web Applications, GCS is widely used as a serverless origin for hosting
Single-Page Applications (SPAs) or static marketing websites (SSG). By placing
an External Application Load Balancer and Cloud CDN in front of a GCS bucket,
you obtain a fast, secure, globally distributed static hosting solution.

## Target Configurations

### 1. Public Static Web Bucket

Configuring a bucket to serve static HTML (indexing `index.html` and `404.html`)
directly.

### 2. Backend Bucket behind Load Balancer & CDN

Keeping the bucket private or public, but routing all client requests through an
HTTP(S) Load Balancer backend bucket with Cloud CDN enabled to cache pages at
Google edge nodes.

## Infrastructure Code (Terraform)

### Public Static Web Bucket Setup

```terraform
resource "google_storage_bucket" "static_website" {
  name          = "static-marketing-website-bucket"
  location      = "US"
  force_destroy = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }
}

# Grant public read access to all objects in the bucket
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.static_website.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
```

### Private Bucket as Load Balancer Backend Bucket with CDN

```terraform
resource "google_storage_bucket" "private_assets" {
  name     = "private-webapp-assets"
  location = "US"
}

# Configure Backend Bucket for Load Balancer
resource "google_compute_backend_bucket" "cdn_backend" {
  name        = "assets-backend-bucket"
  bucket_name = google_storage_bucket.private_assets.name
  enable_cdn  = true
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Memorystore in Web Applications \
description: Describes how Memorystore (Redis) caching is integrated for Web
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:memorystore"]

--------------------------------------------------------------------------------

# Memorystore in Web Applications

Describes how Memorystore (Redis) caching is integrated for Web Applications.

## Integration Details

In Web Applications, Memorystore (Redis) serves as a high-performance session
cache or application cache. It is crucial for deploying Next.js Incremental
Static Regeneration (ISR) on serverless platforms like Cloud Run, ensuring that
cached pages remain consistent across dynamically scaling stateless container
instances.

## Target Configurations

### 1. Cloud Run Next.js ISR Shared Caching

Configuring Memorystore as the centralized cache provider for Next.js ISR
deployed on Cloud Run.

### 2. GKE Cache Cluster via Private Service Access

Provisioning a Memorystore cluster in the GKE cluster's VPC network, providing
low-latency internal cache nodes to web servers.

## Infrastructure Code (Terraform)

### Memorystore Redis Instance with Private IP

```terraform
resource "google_redis_instance" "cache" {
  name           = "app-cache"
  tier           = "BASIC"
  memory_size_gb = 1

  region             = "us-central1"
  authorized_network = "projects/my-project/global/networks/my-vpc"

  # Connect privately
  connect_mode = "PRIVATE_SERVICE_ACCESS"
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Tasks in Web Applications \
description: Describes how Cloud Tasks is integrated and configured for Web
Applications to manage asynchronous background tasks. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_tasks"]

--------------------------------------------------------------------------------

# Cloud Tasks in Web Applications

Describes how Cloud Tasks is integrated and configured for Web Applications.

## Integration Details

In Web Applications, Cloud Tasks is used to queue up long-running or
resource-intensive tasks (e.g. email dispatch, image processing, heavy analytics
compilation) and process them asynchronously via target serverless HTTP
endpoints like Cloud Run.

## Target Configurations

### 1. Asynchronous Task Queue

A standard task queue configuration that buffers and retries failed background
HTTP calls.

## Infrastructure Code (Terraform)

### Cloud Tasks Queue Configuration

```terraform
resource "google_cloud_tasks_queue" "default" {
  name     = "web-background-tasks"
  location = "us-central1"

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 500
  }

  retry_config {
    max_attempts       = 5
    max_backoff        = "3600s"
    max_doublings      = 4
    min_backoff        = "0.100s"
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Run in Web Applications \
description: Describes how Cloud Run is integrated and configured for Web
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_run"]

--------------------------------------------------------------------------------

# Cloud Run in Web Applications

Describes how Cloud Run is integrated and configured for Web Applications.

## Integration Details

In Web Applications, Cloud Run is usually exposed behind an Application Load
Balancer via a Serverless Network Endpoint Group (NEG). This allows developers
to serve containerized frontends and backends with SSL termination, CDN caching,
and custom domain routing.

## Target Configurations

### Private Microservice with Direct VPC Egress

Configuring Cloud Run to reside inside a VPC network using Direct VPC Egress for
secure database/cache access, and setting the ingress level to
`INGRESS_TRAFFIC_INTERNAL_ONLY` to restrict public access.
Invoker permissions (`roles/run.invoker`) should only be given to specific
principals or groups.

## Infrastructure Code (Terraform)

### Private Microservice with Direct VPC Egress

```terraform
resource "google_cloud_run_v2_service" "private_service" {
  name     = "internal-service"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "gcr.io/my-project/db-processor:latest"
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }

    vpc_access {
      network_interfaces {
        network    = "projects/my-project/global/networks/my-vpc"
        subnetwork = "projects/my-project/regions/us-central1/subnetworks/my-subnet"
      }
      egress = "ALL_TRAFFIC" # Route all outbound traffic through the VPC
    }

    service_account = "internal-service-sa@your-project.iam.gserviceaccount.com"
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Firebase Hosting in Web Applications \
description: Describes how Firebase Hosting is configured to serve static assets
and rewrites for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:firebase_hosting"]

--------------------------------------------------------------------------------

# Firebase Hosting in Web Applications

Describes how Firebase Hosting is configured to serve static assets and rewrites
for Web Applications.

## Integration Details

In serverless Web Applications, Firebase Hosting serves as the CDN edge and
hosting layer for static content. It enables developers to integrate static
sites with dynamic backends like Cloud Functions or Cloud Run by specifying URL
rewrite rules inside a local configuration file.

## Target Configurations

### SPA with Cloud Functions API backend

Configuring path rewrites to direct API requests (e.g. `/api/*`) to a Cloud
Function, while serving static index files for all other routes.

## Configuration Code (firebase.json)

An example `firebase.json` configuration specifying hosting redirects and
rewrites:

```json
{
  "hosting": {
    "public": "dist",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**"
    ],
    "rewrites": [
      {
        "source": "/api/**",
        "function": {
          "functionId": "api-backend",
          "region": "us-central1"
        }
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ]
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: App Engine in Web Applications \
description: Describes how App Engine is integrated and configured for Web
Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:app_engine"]

--------------------------------------------------------------------------------

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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Firebase Authentication in Web Applications \
description: Describes how Firebase Authentication manages client identity and
token verification for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:firebase_auth"]

--------------------------------------------------------------------------------

# Firebase Authentication in Web Applications

Describes how Firebase Authentication manages client identity and token
verification for Web Applications.

## Integration Details

In Web Applications, Firebase Authentication manages user login states
(email/password, OAuth, MFA). On successful login, the Firebase SDK provides a
JWT token. The web application's frontend sends this token in request
authorization headers to backends (such as Cloud Run or GKE APIs), which verify
the tokens using the Firebase Admin SDK.

## Target Configurations

### Client Auth token propagation to serverless backend

Sign in client, retrieve ID token, attach as Bearer token to API requests.
Backend verifies the token signature and extracts user claims.

## Example Code (JavaScript / Node.js)

### Client-Side JWT Retrieval

```javascript
import { getAuth, signInWithEmailAndPassword } from "firebase/auth";

const auth = getAuth();
signInWithEmailAndPassword(auth, email, password)
  .then(async (userCredential) => {
    // Get ID Token
    const idToken = await userCredential.user.getIdToken();
    // Send to backend
    fetch('/api/profile', {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });
  });
```

### Server-Side verification (Cloud Run API backend)

```javascript
const admin = require('firebase-admin');
admin.initializeApp();

async function authMiddleware(req, res, next) {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).send('Unauthorized');
  }
  const token = header.split(' ')[1];
  try {
    const decodedToken = await admin.auth().verifyIdToken(token);
    req.user = decodedToken;
    next();
  } catch (error) {
    res.status(403).send('Forbidden');
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Compute Engine in Web Applications \
description: Describes how Compute Engine virtual machines and Managed Instance
Groups (MIGs) are used in Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:compute_engine"]

--------------------------------------------------------------------------------

# Compute Engine in Web Applications

Describes how Compute Engine virtual machines and Managed Instance Groups (MIGs)
are used in Web Applications.

## Integration Details

Compute Engine is best suited for traditional full-stack web applications,
monoliths, or self-hosted database engines (like MySQL/PostgreSQL
primary-replica pairs) that require custom OS configurations or kernel tuning.
Compute Engine Managed Instance Groups (MIGs) provide scalability and high
availability, but stateful MIGs cannot utilize dynamic autoscaling.

## Target Configurations

### 1. Web Application on Stateless MIG with Load Balancer

Running stateless server instances in an autoscaling MIG behind an Application
Load Balancer.

### 2. Self-Managed MySQL Database on Stateful GCE VM

Provisioning a dedicated VM to host a database, using static internal IP
addresses and persistent disk templates to preserve state.

## Infrastructure Code (Terraform)

### Stateless MIG with Autoscaling

```terraform
resource "google_compute_instance_template" "web_template" {
  name_prefix  = "web-server-template-"
  machine_type = "e2-medium"

  disk {
    source_image = "debian-cloud/debian-11"
    auto_delete  = true
    boot         = true
  }

  network_interface {
    network = "default"
  }
}

resource "google_compute_instance_group_manager" "web_mig" {
  name               = "web-app-mig"
  base_instance_name = "web-server"
  zone               = "us-central1-a"

  version {
    instance_template = google_compute_instance_template.web_template.id
  }

  # target_size is managed by the autoscaler
}

resource "google_compute_autoscaler" "web_autoscaler" {
  name   = "web-app-autoscaler"
  zone   = "us-central1-a"
  target = google_compute_instance_group_manager.web_mig.id

  autoscaling_policy {
    max_replicas    = 5
    min_replicas    = 2
    cooldown_period = 60

    cpu_utilization {
      target = 0.6
    }
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Cloud Spanner in Web Applications \
description: Describes how Cloud Spanner is integrated for globally distributed,
strongly consistent Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:cloud_spanner"]

--------------------------------------------------------------------------------

# Cloud Spanner in Web Applications

Describes how Cloud Spanner is integrated for globally distributed, strongly
consistent Web Applications.

## Integration Details

For globally distributed Web Applications, Cloud Spanner serves as a highly
available, multi-region SQL database that guarantees absolute transactional
integrity (ACID) and strong consistency across regions. Spanner is best paired
with multi-regional deployments of Cloud Run or GKE fronted by a Global External
Application Load Balancer.

## Target Configurations

### Multi-Regional Cloud Run to Multi-Region Spanner

Deploying Cloud Run in regional endpoints (e.g., `us-east1`, `europe-west1`) and
accessing a multi-region Cloud Spanner instance via Direct VPC Egress for
low-latency database transactions.

## Infrastructure Code (Terraform)

### Multi-Region Spanner Instance and Database

```terraform
resource "google_spanner_instance" "spanner_inst" {
  config       = "nam-eur-asia1" # Multi-regional configuration (US, Europe, Asia)
  display_name = "Global Web App DB"
  name         = "global-web-db"
  num_nodes    = 1
  edition      = "ENTERPRISE_PLUS"
}

resource "google_spanner_database" "database" {
  instance = google_spanner_instance.spanner_inst.name
  name     = "app_db"
  ddl = [
    "CREATE TABLE Users ( UserId STRING(36) NOT NULL, Email STRING(255), Name STRING(255) ) PRIMARY KEY (UserId)",
    "CREATE TABLE Orders ( UserId STRING(36) NOT NULL, OrderId STRING(36) NOT NULL, OrderDate TIMESTAMP, TotalAmount NUMERIC ) PRIMARY KEY (UserId, OrderId), INTERLEAVE IN PARENT Users ON DELETE CASCADE"
  ]
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: Firestore in Web Applications \
description: Describes how Firestore document databases are integrated and
secured for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:firestore"]

--------------------------------------------------------------------------------

# Firestore in Web Applications

Describes how Firestore document databases are integrated and secured for Web
Applications.

## Integration Details

In Web Applications, Firestore is ideal for real-time collaborative applications
(like document editors, live dashboards) or flexible-schema user profiles. In
Native Mode, clients connect directly to Firestore using client-side SDKs,
bypassing custom API middleware. Access control is managed through declarative
Firestore Security Rules.

## Target Configurations

### 1. Direct Web Client Access with Security Rules

Using Firebase SDKs to read/write Firestore collections directly, secured by
matching auth states in security rules.

### 2. Admin SDK in Serverless (Cloud Run / GKE)

Using the Admin SDK in a secure server-side compute runtime for database
operations, authenticated via IAM roles (Workload Identity for GKE, service
account for Cloud Run).

## Infrastructure Code (Terraform)

### Firestore Database Instance

```terraform
resource "google_firestore_database" "database" {
  name                    = "(default)"
  location_id             = "nam5"
  type                    = "FIRESTORE_NATIVE"
  concurrency_mode        = "OPTIMISTIC"
  app_engine_integration_mode = "DISABLED"
}
```

### Example Firestore Security Rules (firestore.rules)

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only authenticated users can read/write user-owned profiles
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Anyone can read public products, but only admins can write
    match /products/{productId} {
      allow read: if true;
      allow write: if request.auth != null && request.auth.token.admin == true;
    }
  }
}
```

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: External Application Load Balancer in Web Applications \
description: Describes how the External Application Load Balancer routes user
traffic to web application backends. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:external_load_balancer"]

--------------------------------------------------------------------------------

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

--------------------------------------------------------------------------------

type: ArchetypeBestPractice \
title: GKE in Web Applications \
description: Describes how Google Kubernetes Engine (GKE) is integrated and
configured for Web Applications. \
timestamp: 2026-06-20T13:11:30Z \
tags: [archetypes, web_applications, "product:gke"]

--------------------------------------------------------------------------------

# GKE in Web Applications

Describes how Google Kubernetes Engine (GKE) is integrated and configured for
Web Applications.

## Integration Details

For Web Applications, Google Kubernetes Engine (GKE) serves as a robust
container orchestration platform suitable for complex microservices-based
full-stack architectures, API gateways, and stateful applications. It offers
maximum control over cluster networking, container scheduling, and resource
allocation. GKE is exposed to user traffic via GKE Ingress, which provisions an
External Application Load Balancer.

## Target Configurations

### 1. Web Application Fronted by GKE Ingress & IAP

Configuring GKE Ingress to manage routing to stateless pods, fronted by
Identity-Aware Proxy (IAP) for user authentication.

### 2. Private GKE Connection to Cloud SQL via Proxy Sidecar

Enabling pods in a private, VPC-native GKE cluster to securely write to Cloud
SQL using the Cloud SQL Auth Proxy sidecar container.

### 3. Cost-Optimized Spot VM Node Pools

Deploying stateless frontend pods on GKE Spot VMs to drastically reduce compute
costs, configuring fallback pools with standard VMs.

## Infrastructure Code (Terraform)

### GKE Ingress with Google-Managed Certificate

```terraform
# Define GKE cluster (VPC-Native)
resource "google_container_cluster" "web_cluster" {
  name     = "web-app-cluster"
  location = "us-central1"

  # Enable VPC-native traffic routing (required for Private IPs/NEGs)
  ip_allocation_policy {}
}

# Managed SSL certificate for Ingress
resource "google_compute_managed_ssl_certificate" "default" {
  name = "web-app-ssl-cert"

  managed {
    domains = ["webapp.example.com"]
  }
}
```

### Pod Spec with Cloud SQL Auth Proxy Sidecar

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ecommerce-api
spec:
  replicas: 3
  template:
    metadata:
      labels:
        app: ecommerce-api
    spec:
      containers:
      - name: api-app
        image: gcr.io/my-project/ecommerce-api:latest
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          value: "127.0.0.1"
      # Cloud SQL Auth Proxy Sidecar
      - name: cloud-sql-proxy
        image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.1.0
        args:
          - "--structured-logs"
          - "--port=5432"
          - "my-project:us-central1:my-database"
        securityContext:
          runAsNonRoot: true
```
