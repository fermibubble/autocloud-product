---
type: PerProductBestPractice  
title: Firebase Authentication in Web Applications  
description: Describes how Firebase Authentication manages client identity and token verification for Web Applications.  
timestamp: 2026-06-20T13:11:30Z  
tags: [archetypes, web_applications, "product:firebase_auth"]

---

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
