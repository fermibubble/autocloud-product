"""Outcome collector: the loop that turns episodes into LABELED history.

Every principle downstream of memory ("learn only from labeled outcomes,
never the agent's own verdicts") depends on something producing labels.
This is that something: for each episode awaiting outcome it observes
ground truth at the 30m / 2h / 24h horizons (scaled by SIM_TIME_SCALE,
same clock the relay compresses) and, at the final horizon, derives the
label and closes the episode:

    rolled_back  — the world recorded a rollback of the service
    regressed    — ground-truth SLOs breach policy thresholds
    healthy      — neither

Ground truth comes from the sim's world face (/world/services `truth`
block) — in production this reads your monitoring system, NOT the signed
observation path the reviewer used: labels must be independent of the
evidence chain they will later judge.

Crash-safe: horizons are idempotent per (episode, horizon) server-side,
and on restart the collector re-derives pending work from
GET /intel/episodes?status=awaiting_outcome.

Run: SIM_TIME_SCALE=0.02 uv run python outcome_collector.py
"""

import json
import os
import threading
import time
import urllib.request

WORLD = os.environ.get("WORLD_API", "http://127.0.0.1:7621")
INTEL = os.environ.get("INTEL_API", "http://127.0.0.1:7611")
SCALE = float(os.environ.get("SIM_TIME_SCALE", "0.02"))

# Label thresholds mirror the policy pack's hard rules (rollout-slo@1).
P99_MAX_MS = 250.0
ERR_MAX = 0.005

HORIZONS = [("30m", 30), ("2h", 120), ("24h", 1440)]


def _req(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def observe(service_name: str) -> dict:
    state = _req(f"{WORLD}/world/services")[service_name]
    return {
        "p99_ms": state["truth"]["p99_ms"],
        "error_rate": state["truth"]["error_rate"],
        "rps": state["truth"]["rps"],
        "rolled_back": state["rolled_back"],
        "revision": state["revision"],
    }


def label_from(slo: dict) -> str:
    if slo["rolled_back"]:
        return "rolled_back"
    if slo["p99_ms"] > P99_MAX_MS or slo["error_rate"] > ERR_MAX:
        return "regressed"
    return "healthy"


def collect_episode(episode: dict) -> None:
    episode_id = episode["episode_id"]
    service_name = episode["service_uid"].split("/")[-3]
    anchor = time.time()  # horizons run from when the collector picks it up
    for horizon, minutes in HORIZONS:
        target = anchor + minutes * 60 * SCALE
        while time.time() < target:
            time.sleep(min(1.0, target - time.time()))
        slo = observe(service_name)
        final = horizon == HORIZONS[-1][0]
        # A redeploy mid-soak means the truth now describes the NEWER
        # revision — labeling this episode from it would poison the
        # labeled corpus. Record the observation, never the label.
        superseded = (episode.get("revision_to")
                      and slo["revision"] != episode["revision_to"]
                      and not slo["rolled_back"])
        payload = {
            "horizon": horizon, "slo": slo,
            "rollback_detected": slo["rolled_back"],
            "source": "collector",
            "notes": (f"superseded by {slo['revision']} mid-soak; not labeled"
                      if superseded else f"ground truth at {horizon} (scaled)"),
        }
        if final and not superseded:
            payload["final_label"] = label_from(slo)
        try:
            _req(f"{INTEL}/intel/episodes/{episode_id}/outcome", payload)
        except Exception as exc:
            print(f"collector: {episode_id} {horizon} not recorded ({exc})")
            return
        if final and superseded:
            print(f"collector: {episode_id} superseded by {slo['revision']}; left unlabeled")
        else:
            print(f"collector: {episode_id} {horizon} p99={slo['p99_ms']} "
                  f"err={slo['error_rate']}"
                  + (f" -> label {payload['final_label']}" if final else ""))


def main() -> None:
    print(f"collector: labeling awaiting_outcome episodes (scale {SCALE})")
    seen: set[str] = set()
    while True:
        try:
            pending = _req(f"{INTEL}/intel/episodes?status=awaiting_outcome")
        except Exception as exc:
            print(f"collector: intel unreachable ({exc}); retrying")
            time.sleep(5)
            continue
        for episode in pending:
            if episode["episode_id"] in seen:
                continue
            if episode["episode_id"].startswith("fx_"):
                continue  # fixtures carry their own labels
            seen.add(episode["episode_id"])
            threading.Thread(target=collect_episode, args=(episode,),
                             daemon=True).start()
        time.sleep(3)


if __name__ == "__main__":
    main()
