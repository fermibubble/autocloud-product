---
type: PerProductBestPractice  
title: Connection-Draining & Capacity Routing  
description: Enforce connection-draining and capacity-based routing.  
timestamp: 2026-06-20T13:11:30Z  
tags: [best_practices, reliability, "product:gke", "product:compute_engine"]

---

# Connection-Draining & Capacity Routing

For long-lived, multi-modal streaming protocols (such as WebSockets in Gemini
Live duplex connections) and extended inference queuing, shift away from
round-robin or latency-based distribution. Enforce connection-draining and
capacity-based routing at the traffic management layers to prevent replica
overloading.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
title: Compute Engine in Internal Serving \
description: Describes how Compute Engine is configured for Internal Serving. \
timestamp: 2026-06-20T13:00:00Z \
tags: [archetypes, internal_serving, "product:compute_engine"]

--------------------------------------------------------------------------------

# Compute Engine

**Compute Engine** offers IaaS, providing maximum control over virtual machines,
suitable for lift-and-shift or highly customized environments, relying on
internal DNS and firewall rules for internal communication.

## Usage

*   Typically deployed in Managed Instance Groups (MIGs) and placed behind an
    Internal Application Load Balancer.
*   Often used for data processing tasks, legacy monolithic applications, or
    applications requiring specific OS or kernel configurations.

## Best Practices

*   **Private Google Access:** For internal services on Compute Engine to
    securely access Google APIs (like BigQuery or Cloud Storage) without
    traversing the public internet, Private Google Access and specific DNS
    configurations are essential.
*   Use internal IPs and Internal Load Balancers rather than external IPs for
    internal workloads.

## Anti-patterns

*   Assigning external IP addresses to Compute Engine instances serving purely
    internal workloads.

--------------------------------------------------------------------------------

type: PerProductBestPractice \
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
