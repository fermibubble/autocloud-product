---
type: PerProductBestPractice  
title: Firestore in Web Applications  
description: Describes how Firestore document databases are integrated and secured for Web Applications.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, web_applications, "product:firestore"]

---

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
