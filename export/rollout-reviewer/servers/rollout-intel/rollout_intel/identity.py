"""Canonical service identity (research §4): catalog first, labels second,
platform metadata third, inference last — and inferred identities are
CANDIDATES, never silently authoritative.

v1 resolves from the product's service catalog (catalog/services.yaml) with
a deploy-event fallback that lands as status=candidate.
"""

import yaml

from sqlalchemy import case, or_, select

from .db import Db, row_dict
from .models import Service


def load_catalog(db: Db, path: str) -> int:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    count = 0
    for entry in doc.get("services", []):
        uid = (f"svc://{entry['tenant']}/{entry['name']}/"
               f"{entry['environment']}/{entry['region']}")
        svc = {
            "service_uid": uid,
            "name": entry["name"],
            "environment": entry["environment"],
            "region": entry["region"],
            "aliases": entry.get("aliases", []),
            "source": "catalog",
            "status": "confirmed",
        }
        # Pass through only keys the entry actually carries, so a sparse
        # catalog re-load preserves stored metadata (upsert_service's
        # absent-key guard) instead of blanking it with defaults. Defaults
        # apply only on first insert.
        for key, default in (("runtime", "cloud-run"),
                             ("architecture_version", "v1"), ("owner", "")):
            if key in entry:
                svc[key] = entry[key]
            elif db.get_service(uid) is None:
                svc[key] = default
        db.upsert_service(svc)
        count += 1
    return count


def resolve(db: Db, deploy_event: dict) -> dict:
    """Deploy event -> service row. Catalog match by name-or-alias + region
    wins; a confirmed row always outranks a pre-existing inferred candidate
    for the same name (the module invariant: inference never silently
    beats the catalog). Otherwise an inferred candidate row is created,
    visibly non-authoritative."""
    name = deploy_event.get("service", "")
    region = deploy_event.get("region", "us-central1")
    with db.session() as s:
        row = s.execute(
            select(Service)
            .where(Service.region == region,
                   or_(Service.name == name,
                       # aliases_json is a JSON array of quoted names; the
                       # quoted-token LIKE stops 'checkout' matching
                       # 'checkout-v2'.
                       Service.aliases_json.like(f'%"{name}"%')))
            .order_by(case((Service.status == "confirmed", 0), else_=1),
                      Service.service_uid)
            .limit(1)
        ).scalars().first()
        if row:
            return row_dict(row)
    uid = f"svc://inferred/{name}/prod/{region}"
    db.upsert_service({
        "service_uid": uid, "name": name, "environment": "prod", "region": region,
        "source": "inferred", "status": "candidate",
    })
    with db.session() as s:
        return row_dict(s.get(Service, uid))
