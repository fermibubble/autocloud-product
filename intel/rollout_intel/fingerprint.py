"""Deterministic rollout fingerprints (research §8): the retrieval key that
semantic similarity can't provide. Built from the deploy event + service
identity; compared by Jaccard over the flattened trait set."""


def from_deploy_event(event: dict, service: dict) -> dict:
    return {
        "fingerprint_version": "v1",
        "service_family": service["name"].rsplit("-", 1)[0],
        "runtime": service.get("runtime") or "cloud-run",
        "environment": service.get("environment", "prod"),
        # The deploy event is the authority on which architecture is being
        # rolled out; the service row only remembers the last one seen —
        # this asymmetry is what makes architecture-change detection real.
        "architecture_version": (event.get("architecture_version")
                                 or service.get("architecture_version", "v1")),
        "strategy": event.get("strategy", "unknown"),
        "change_classes": sorted(event.get("change_classes", [])),
        "image_digest": event.get("image_digest", ""),
    }


def traits(fp: dict) -> set[str]:
    out = {
        f"runtime:{fp.get('runtime')}",
        f"strategy:{fp.get('strategy')}",
        f"arch:{fp.get('architecture_version')}",
        f"family:{fp.get('service_family')}",
    }
    for c in fp.get("change_classes", []):
        out.add(f"change:{c}")
    return out


def jaccard(a: dict, b: dict) -> float:
    ta, tb = traits(a), traits(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
