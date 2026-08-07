"""rollout-scheduler relay: the durable clock of the review loop.

Native harness triggers are a deferred feature, so this relay owns
scheduling (the travel-product relay pattern, grown up): it polls the
deployment feed, creates an episode in rollout-intel, then walks the
T+0/5/15/30 ladder — one NEW harness session per checkpoint (harness
checkpoints are crash-recovery only; cross-wake-up state lives in
rollout-intel, which is why this process can die at any time and resume
from GET /intel/episodes?status=in_progress).

Each wake-up session's input carries the episode header the reviewer's
skill teaches it to parse:

    EPISODE: ep_...
    STAGE: T+5
    SERVICE: svc://autocloud/demo-healthy/prod/us-central1
    PRIOR: T+0 healthy(pass)

SIM_TIME_SCALE compresses the ladder for golden runs (0.02 -> T+30 fires
at 36s). Requires ENSEMBLE_TOKEN (autocloud tenant).

Run: ENSEMBLE_TOKEN=... SIM_TIME_SCALE=0.02 uv run python relay.py
"""

import json
import os
import threading
import time
import urllib.request

WORLD = os.environ.get("WORLD_API", "http://127.0.0.1:7621")
INTEL = os.environ.get("INTEL_API", "http://127.0.0.1:7611")
API = os.environ.get("ENSEMBLE_API", "http://localhost:8088")
TOKEN = os.environ.get("ENSEMBLE_TOKEN", "")
AGENT = os.environ.get("REVIEWER_AGENT", "rollout-reviewer-scripted")
SCALE = float(os.environ.get("SIM_TIME_SCALE", "0.02"))

STAGES = [("T+0", 0), ("T+5", 5), ("T+15", 15), ("T+30", 30)]


def _req(url: str, body: dict | None = None, authed: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    if authed and TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def run_episode(episode: dict) -> None:
    episode_id = episode["episode_id"]
    service_uid = episode["service_uid"]
    started = time.time()
    done = {c["stage"] for c in _req(f"{INTEL}/intel/episodes/{episode_id}")["checkpoints"]
            if c.get("completed_at")}
    prior = "none"
    for stage, offset_min in STAGES:
        if stage in done:
            continue
        target = started + offset_min * 60 * SCALE
        while time.time() < target:
            time.sleep(min(1.0, target - time.time()))
        service_name = service_uid.split("/")[-3] if "/" in service_uid else service_uid
        input_text = (
            f"EPISODE: {episode_id}\n"
            f"STAGE: {stage}\n"
            f"SERVICE: {service_uid}\n"
            f"CASE: {stage}@{service_name}\n"
            f"PRIOR: {prior}\n\n"
            f"Run the {stage} checkpoint of the rollout validation protocol "
            f"for this episode."
        )
        session = _req(f"{API}/v1/sessions", {"agent": AGENT, "input": input_text},
                       authed=True)
        session_id = session["id"]
        _req(f"{INTEL}/intel/episodes/{episode_id}/checkpoints",
             {"stage": stage, "session_id": session_id})
        print(f"relay: {episode_id} {stage} -> session {session_id}")

        deadline = time.time() + 600
        while time.time() < deadline:
            status = _req(f"{API}/v1/sessions/{session_id}", authed=True)["status"]
            if status in ("completed", "failed", "cancelled", "failed_budget"):
                break
            time.sleep(2)

        cps = _req(f"{INTEL}/intel/episodes/{episode_id}")["checkpoints"]
        this = next((c for c in cps if c["stage"] == stage), {})
        if this.get("completed_at"):
            prior = f"{stage} {this.get('stage_verdict')}({this.get('policy_status')})"
            # rollout-intel owns scheduling: no next check means the ladder
            # is over (last stage, or a governed stabilization window ended
            # it early) — the relay never second-guesses that.
            if this.get("next_check_at") is None:
                print(f"relay: episode {episode_id} ladder ended by scheduler at {stage}")
                break
        else:
            prior = f"{stage} NOT RECORDED (session {status})"
            print(f"relay: WARNING {episode_id} {stage} session ended without record_checkpoint")
    print(f"relay: episode {episode_id} ladder complete")


def main() -> None:
    print(f"relay: watching {WORLD}/world/deployments -> agent {AGENT} (scale {SCALE})")
    # Resume anything mid-flight from a previous relay life.
    for episode in _req(f"{INTEL}/intel/episodes?status=in_progress"):
        print(f"relay: resuming {episode['episode_id']}")
        threading.Thread(target=run_episode, args=(episode,), daemon=True).start()

    seen = len(_req(f"{WORLD}/world/deployments"))
    while True:
        events = _req(f"{WORLD}/world/deployments")
        for event in events[seen:]:
            episode = _req(f"{INTEL}/intel/episodes", event)
            print(f"relay: deploy {event['service']} -> episode {episode['episode_id']} "
                  f"(identity {episode.get('identity_status')})")
            # Fast-forward hand-off: env-gated, fire-and-forget — the relay
            # owns the clock, FF only receives the deadline. A failed or
            # hung FF (bounded by _req's timeout) never breaks the loop.
            ff = os.environ.get("FF_API")
            if ff:
                try:
                    _req(f"{ff}/ff/requests", {
                        "episode_id": episode["episode_id"],
                        "service": event["service"],
                        "deploy_event": event,
                        "deadline_s": 30 * 60 * SCALE,
                        "budget": {"max_probe_seconds": 60, "max_steps": 6}})
                except Exception as exc:
                    print(f"relay: WARNING fast-forward hand-off failed: {exc}")
            threading.Thread(target=run_episode, args=(episode,), daemon=True).start()
        seen = len(events)
        time.sleep(2)


if __name__ == "__main__":
    main()
