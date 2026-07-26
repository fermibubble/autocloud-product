---
type: PerProductBestPractice  
title: Firebase Hosting in Web Applications  
description: Describes how Firebase Hosting is configured to serve static assets and rewrites for Web Applications.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, web_applications, "product:firebase_hosting"]

---

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
