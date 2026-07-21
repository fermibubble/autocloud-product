"""Canonical service identity (research §4): catalog first, labels second,
platform metadata third, inference last — and inferred identities are
CANDIDATES, never silently authoritative.

v1 resolves from the product's service catalog (catalog/services.yaml) with
a deploy-event fallback that lands as status=candidate.
"""

import yaml

from .db import Db


def load_catalog(db: Db, path: str) -> int:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    count = 0
    for entry in doc.get("services", []):
        uid = (f"svc://{entry['tenant']}/{entry['name']}/"
               f"{entry['environment']}/{entry['region']}")
        db.upsert_service({
            "service_uid": uid,
            "name": entry["name"],
            "environment": entry["environment"],
            "region": entry["region"],
            "runtime": entry.get("runtime", "cloud-run"),
            "architecture_version": entry.get("architecture_version", "v1"),
            "owner": entry.get("owner", ""),
            "aliases": entry.get("aliases", []),
            "source": "catalog",
            "status": "confirmed",
        })
        count += 1
    return count


def resolve(db: Db, deploy_event: dict) -> dict:
    """Deploy event -> service row. Catalog match by name+region wins;
    otherwise an inferred candidate row is created (visibly non-authoritative)."""
    name = deploy_event.get("service", "")
    region = deploy_event.get("region", "us-central1")
    row = db.one(
        "SELECT * FROM services WHERE name=? AND region=? ORDER BY status LIMIT 1",
        (name, region),
    )
    if row:
        return row
    uid = f"svc://inferred/{name}/prod/{region}"
    db.upsert_service({
        "service_uid": uid, "name": name, "environment": "prod", "region": region,
        "source": "inferred", "status": "candidate",
    })
    return db.one("SELECT * FROM services WHERE service_uid=?", (uid,))
