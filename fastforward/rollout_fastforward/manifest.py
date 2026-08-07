"""Change-manifest canonicalization, digest, and feature-trait extraction.

The manifest is the only input the hazard compiler trusts: traits are
extracted by deterministic keyword maps (no inference), so the same change
always compiles to the same hazards with the same ids.
"""

import hashlib
import json

DEP_CLASSES = {
    "pool": ["pool"],
    "auth": ["auth", "oauth", "token", "cred"],
    "http": ["http", "client"],
    "retry": ["retry"],
    "db": ["pg", "mysql", "sql", "mongo"],
}

CFG_CLASSES = {
    "retry": ["retry"],
    "timeout": ["timeout"],
    "ttl": ["ttl"],
    "expiry": ["expiry", "expire"],
    "pool": ["pool"],
    "queue": ["queue"],
    "batch": ["batch"],
    "cache": ["cache"],
}

CODE_AREAS = {
    "connection": ["connection", "conn", "pool"],
    "auth": ["auth", "cred", "token"],
    "retry": ["retry", "backoff"],
    "queue": ["queue", "consumer", "producer"],
    "schedule": ["cron", "schedule", "timer"],
    "cache": ["cache"],
}


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def canonicalize(deploy_event_or_manifest: dict) -> dict:
    """Normalize a deploy event (change_manifest key) or bare manifest to
    {"items":[...]} with items sorted by (kind, name) and paths sorted."""
    m = deploy_event_or_manifest.get("change_manifest", deploy_event_or_manifest)
    items = []
    for it in m.get("items", []):
        it = dict(it)
        if isinstance(it.get("paths"), list):
            it["paths"] = sorted(it["paths"])
        items.append(it)
    items.sort(key=lambda it: (str(it.get("kind", "")), str(it.get("name", ""))))
    return {"items": items}


def digest(deploy_event_or_manifest: dict) -> str:
    return "mf_" + hashlib.sha256(_canonical(canonicalize(deploy_event_or_manifest))).hexdigest()[:16]


def _classes(name: str, class_map: dict) -> list[str]:
    return [cls for cls, kws in class_map.items() if any(kw in name for kw in kws)]


def features(deploy_event_or_manifest: dict) -> list[str]:
    """Sorted trait strings; substring match on lowercase name/path."""
    out: set[str] = set()
    for it in canonicalize(deploy_event_or_manifest)["items"]:
        kind = it.get("kind")
        name = str(it.get("name", ""))
        low = name.lower()
        if kind == "dependency":
            out.add(f"dep:{name}")
            out.update(f"dep-class:{c}" for c in _classes(low, DEP_CLASSES))
        elif kind == "config":
            out.add(f"cfg:{name}")
            out.update(f"cfg-class:{c}" for c in _classes(low, CFG_CLASSES))
        elif kind == "code":
            for path in it.get("paths", []):
                out.update(f"code-touch:{c}" for c in _classes(str(path).lower(), CODE_AREAS))
        elif kind == "flag":
            out.add(f"flag:{name}")
        elif kind == "schema":
            out.add(f"schema:{name}")
            out.add("kind:schema")
    return sorted(out)
