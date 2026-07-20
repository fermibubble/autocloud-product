"""demo-service: the tiny deployable the rollout-reviewer reviews.
Deploy to Cloud Run:  gcloud run deploy demo-service --source demo-service/
Emits request logs and a /healthz; that's its entire job - to be observed."""
import http.server, json, os, random

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code = 200 if self.path != "/flaky" or random.random() > 0.3 else 500
        body = json.dumps({"service": "demo-service", "path": self.path,
                           "revision": os.environ.get("K_REVISION", "local")}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"demo-service on :{port}")
    http.server.ThreadingHTTPServer(("", port), H).serve_forever()
