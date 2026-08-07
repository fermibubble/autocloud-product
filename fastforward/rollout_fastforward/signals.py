"""Signal experiments: project the candidate's future from REAL telemetry.

A signal alone never mints a counterexample — it has no event sequence.
Its strongest verdict is projected_boundary; and without a stable profile
it cannot call anything flat, so a missing baseline degrades to
inconclusive_signal (escalate to a probe), never to a pass. Envelopes come
signed from gcp-observe's /observe/metric and are verified here before a
single point is trusted.
"""

import calendar
import os
import time

import httpx

from . import envelope
from .profiles import z as profile_z
from .stats import theil_sen, time_to_threshold

# Metric types per signal template; the FIRST is the projected axis, the
# rest corroborate (must not contradict a harm call).
METRICS = {
    "growth_projection": ["run.googleapis.com/container/open_connections"],
    "queue_drift_projection": ["run.googleapis.com/container/queue_depth",
                               "run.googleapis.com/container/retry_count"],
}

# Harm level the projection is measured against (per template).
LEVELS = {"growth_projection": 1000.0, "queue_drift_projection": 500.0}

# Fingerprint under which signal (telemetry) profiles are stored: telemetry
# baselines are per-service, not per-probe-spec.
SIGNAL_FP = {"spec_digest": "telemetry-v1", "sim_seeded": True,
             "runtime": "gcp-observe"}

Z_HARM = 3.0           # MAD-z beyond which a slope leaves the stable envelope
HORIZON_MIN = 1440.0   # policy horizon (minutes) a projected breach must hit
WINDOW_MINUTES = 30
MIN_POINTS = 4


def _inconclusive(reason: str, measurements: dict | None = None) -> dict:
    return {"disposition": "inconclusive_signal", "reason": reason,
            "measurements": measurements or {}, "observation_ids": []}


def _minutes(iso: str) -> float:
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")) / 60.0


def _fetch(base: str, service: str, metric_type: str) -> dict:
    resp = httpx.get(f"{base}/observe/metric",
                     params={"service": service, "type": metric_type,
                             "minutes": WINDOW_MINUTES}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _points(env: dict) -> list[tuple[float, float]]:
    for s in env.get("payload", {}).get("series", []):
        pts = [(_minutes(p["end"]), float(p["value"]))
               for p in s.get("points", []) if p.get("value") is not None]
        if pts:
            return sorted(pts)
    return []


def run_signal(step: dict, hazard: dict, service: str, profiles,
               deadline: float | None, base: str | None = None,
               deployed_at: float | None = None) -> dict:
    """One signal experiment -> step result with a disposition in
    {projected_boundary, bounded_within_envelope, inconclusive_signal}.
    With deployed_at set, only points at/after the deploy are fitted —
    pre-deploy telemetry describes the OLD revision, and a window that
    barely covers the candidate cannot certify it flat."""
    template = step.get("template", "")
    if template not in METRICS:
        return _inconclusive(f"unknown signal template {template!r}")
    if deadline is not None and time.time() > deadline:
        return _inconclusive("deadline passed before signal ran")
    base = base or os.environ.get("OBSERVE_API", "http://127.0.0.1:7601")

    fits, obs_ids = {}, []
    for metric_type in METRICS[template]:
        try:
            env = _fetch(base, service, metric_type)
        except Exception as exc:
            return _inconclusive(f"telemetry fetch failed: {exc}")
        ok, why = envelope.verify(env)
        if not ok:
            return _inconclusive(f"unverified envelope: {why}")
        if env.get("scope", {}).get("service") not in ("", service):
            return _inconclusive("envelope scoped to a different service")
        pts = _points(env)
        if deployed_at is not None:
            pts = [(x, y) for x, y in pts if x * 60.0 >= deployed_at]
        if len(pts) < MIN_POINTS:
            return _inconclusive(f"too few post-deploy points for {metric_type} "
                                 f"({len(pts)} < {MIN_POINTS})")
        fits[metric_type] = dict(theil_sen(pts), n=len(pts),
                                 current=pts[-1][1])
        obs_ids.append(env["observation_id"])

    primary = fits[METRICS[template][0]]
    stats = profiles.get(service, template, SIGNAL_FP) if profiles else None
    measurements = {"metric_fits": fits, "level": LEVELS[template],
                    "profile": stats}
    if stats is None:
        # No stable envelope to compare against: flat cannot be verified
        # flat. Never a pass-by-default.
        return _inconclusive("no stable telemetry profile", measurements)

    z_lo = profile_z(primary["lo"], stats, "slope")
    z_hi = profile_z(primary["hi"], stats, "slope")
    tt = time_to_threshold(primary["current"], primary["slope"],
                           LEVELS[template], 1.0)  # slope is per minute
    measurements.update({"z_lo": z_lo, "z_hi": z_hi,
                         "time_to_threshold_min": tt})
    corroborated = all(f["slope"] > 0 for m, f in fits.items()
                       if m != METRICS[template][0]) if len(fits) > 1 else True

    if z_lo > Z_HARM and primary["lo"] > 0 and tt <= HORIZON_MIN and corroborated:
        return {"disposition": "projected_boundary",
                "reason": f"slope CI floor z={z_lo:.1f} above stable envelope; "
                          f"projected breach in {tt:.0f}min (< {HORIZON_MIN:.0f})",
                "measurements": measurements, "observation_ids": obs_ids}
    if z_hi < Z_HARM and z_lo > -Z_HARM:
        return {"disposition": "bounded_within_envelope",
                "reason": "slope CI within the stable telemetry envelope",
                "measurements": measurements, "observation_ids": obs_ids}
    out = _inconclusive("slope CI straddles the stable envelope", measurements)
    out["observation_ids"] = obs_ids
    return out
