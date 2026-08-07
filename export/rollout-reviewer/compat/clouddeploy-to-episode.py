#!/usr/bin/env python3
"""Bridge Cloud Deploy discovery into episode creation (stdlib only).

The legacy skill ran `gcloud deploy releases describe` / `rollouts list`
INSIDE every review session. In the trustworthy layout that discovery
moves into your clock/orchestration layer: run your existing gcloud
command there, feed its output (or plain flags) to this script, and it
creates the durable episode the review sessions start from.

Usage (flags):
  clouddeploy-to-episode.py --service payment-gateway --project my-proj \
      --region us-central1 --from-revision v1.44.2 --to-revision v1.45.0 \
      [--strategy canary] [--image-digest sha256:...] \
      [--change-class application_binary] [--intel http://127.0.0.1:7611] [--dry-run]

Usage (gcloud JSON):
  gcloud deploy releases describe R --delivery-pipeline P --region us-central1 \
      --project my-proj --format=json | clouddeploy-to-episode.py --from-json - \
      --service payment-gateway [--intel ...]
  (best-effort field extraction from the release description; flags
   override anything extracted)

Prints the created episode_id. Idempotence is yours: call once per
deploy event, not per checkpoint.
"""
import argparse
import json
import sys
import time
import urllib.request


def from_gcloud_json(doc: dict) -> dict:
    """Best-effort extraction from `gcloud deploy releases describe` output."""
    out = {}
    # Image digest from the first artifact build, when present.
    for art in (doc.get("buildArtifacts") or []):
        tag = art.get("tag", "")
        if "@sha256:" in tag:
            out["image_digest"] = "sha256:" + tag.split("@sha256:")[-1]
            break
    name = doc.get("name", "")
    if "/releases/" in name:
        out["to_revision"] = name.split("/releases/")[-1]
    if doc.get("deliveryPipeline"):
        out.setdefault("labels", {})["delivery_pipeline"] = doc["deliveryPipeline"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--project", default="")
    ap.add_argument("--region", default="")
    ap.add_argument("--from-revision", default="")
    ap.add_argument("--to-revision", default="")
    ap.add_argument("--strategy", default="canary")
    ap.add_argument("--image-digest", default="")
    ap.add_argument("--change-class", action="append", default=[],
                    help="repeatable; defaults to application_binary")
    ap.add_argument("--from-json", help="gcloud describe JSON file, or - for stdin")
    ap.add_argument("--intel", default="http://127.0.0.1:7611")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    extracted = {}
    if args.from_json:
        raw = sys.stdin.read() if args.from_json == "-" else open(args.from_json).read()
        extracted = from_gcloud_json(json.loads(raw))

    event = {
        "type": "deployment_completed",
        "service": args.service,
        "project": args.project or extracted.get("project", ""),
        "region": args.region or extracted.get("region", ""),
        "from_revision": args.from_revision or extracted.get("from_revision", ""),
        "to_revision": args.to_revision or extracted.get("to_revision", ""),
        "image_digest": args.image_digest or extracted.get("image_digest", ""),
        "strategy": args.strategy,
        "change_classes": args.change_class or ["application_binary"],
        "at": time.time(),
    }
    if not event["to_revision"]:
        sys.exit("error: --to-revision missing and not extractable from JSON")

    if args.dry_run:
        print(json.dumps(event, indent=2))
        return 0

    req = urllib.request.Request(
        f"{args.intel.rstrip('/')}/intel/episodes",
        data=json.dumps(event).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        episode = json.loads(resp.read())
    print(episode.get("episode_id", json.dumps(episode)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
