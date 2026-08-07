#!/usr/bin/env python3
"""Dynamic checkpoint scheduling — end-to-end proof (in-process).

Exercises the real Intel service against a CUSTOM policy ladder to prove
the schedule is policy-owned, proposals are clamped, and the ladder
closes only through governed paths:

  1. The policy's ladder replaces the legacy stage names entirely.
  2. get_context_pack exposes the schedule contract to the agent.
  3. No proposal -> the ladder chain decides next_check_at.
  4. A loosening proposal is clamped to max_interval; a tightening one
     is clamped up to min_interval; in-bounds proposals are honored.
  5. On the final stage a proposal cannot extend the ladder.
  6. Exit criteria (N consecutive healthy + min soak) close the ladder
     early — and every next_check decision lands in the audit trail.
  7. A policy WITHOUT a checkpoints block gets the legacy ladder.

Run: uv run --project servers/rollout-intel python scripts/test-dynamic-clock.py
"""

import json
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "servers" / "rollout-intel"))

from rollout_intel import service as svc  # noqa: E402
from rollout_intel.policy import PolicyPack  # noqa: E402

CUSTOM_POLICY = """\
name: custom-clock
version: 7
rules: []
checkpoints:
  ladder:
    - {stage: "C+0", offset_minutes: 0}
    - {stage: "C+10", offset_minutes: 10}
    - {stage: "C+45", offset_minutes: 45}
  bounds:
    min_interval_minutes: 2
    max_interval_minutes: 60
  exit:
    consecutive_healthy: 2
    min_soak_minutes: 2
outcome_horizons: ["1h", "24h", "7d"]
"""

LEGACY_POLICY = """\
name: legacy-shape
version: 1
rules: []
"""

fails = 0


def check(name, ok):
    global fails
    print(("PASS" if ok else "FAIL"), "-", name)
    fails += 0 if ok else 1


def deploy_event(n):
    return {"type": "deployment_completed", "service": "demo-healthy",
            "project": "sim-project", "region": "us-central1",
            "from_revision": f"r{n}", "to_revision": f"r{n + 1}",
            "image_digest": f"sha256:{n:03d}", "strategy": "canary",
            "change_classes": ["application_binary"], "at": time.time()}


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dynclock-"))
    (tmp / "custom.yaml").write_text(CUSTOM_POLICY)
    (tmp / "legacy.yaml").write_text(LEGACY_POLICY)

    # 7. Back-compat: no checkpoints block -> legacy ladder.
    legacy = PolicyPack(str(tmp / "legacy.yaml"))
    check("policy without checkpoints block gets legacy ladder",
          legacy.stages == ["T+0", "T+5", "T+15", "T+30"]
          and legacy.next_chain["T+0"] == 5 and legacy.next_chain["T+30"] is None
          and legacy.outcome_horizons == ["30m", "2h", "24h"])

    intel = svc.Intel(str(tmp / "intel.db"), str(tmp / "custom.yaml"),
                      str(ROOT / "servers" / "rollout-intel" / "catalog" / "services.yaml"))

    # 1. Policy owns the ladder.
    check("custom ladder replaces legacy stage names",
          intel.pack.stages == ["C+0", "C+10", "C+45"])
    ep1 = intel.create_episode(deploy_event(1))["episode_id"]
    try:
        intel.open_checkpoint(ep1, "T+5", "s")
        check("legacy stage name rejected under custom policy", False)
    except ValueError as exc:
        check("legacy stage name rejected under custom policy", "ladder" in str(exc))

    # 2. The schedule contract reaches the agent.
    intel.open_checkpoint(ep1, "C+0", "s1")
    ctx = intel.context_pack(ep1)
    sched = ctx.get("checkpoint_schedule", {})
    check("context pack exposes schedule (ladder+bounds+exit+horizons)",
          [s["stage"] for s in sched.get("ladder", [])] == ["C+0", "C+10", "C+45"]
          and sched["bounds"]["max_interval_minutes"] == 60
          and sched["exit"]["consecutive_healthy"] == 2
          and sched["outcome_horizons"] == ["1h", "24h", "7d"]
          and "never a proposal" in sched.get("note", ""))

    # 3. No proposal -> ladder chain (C+0 -> C+10 = 10 minutes).
    r = intel.record(ep1, "C+0", [], "insufficient-evidence", "no evidence yet", "r", [], [])
    check("ladder chain decides when no proposal is made",
          r.get("next_check_at") == "+10m" and r["next_check"]["source"] == "ladder")

    # 4a. Loosening proposal clamped to max_interval (default C+10->C+45 = 35m).
    intel.open_checkpoint(ep1, "C+10", "s2")
    r = intel.record(ep1, "C+10", [], "insufficient-evidence", "s", "r", [], [],
                     next_check_proposal_minutes=120,
                     next_check_reason="low traffic: 5000 samples need ~2h")
    p = r["next_check"]["proposal"]
    check("loosening proposal clamped to max_interval",
          r["next_check_at"] == "+60m" and p["clamped"] and p["direction"] == "loosen"
          and r["next_check"]["source"] == "proposal")

    # 4b. Tightening proposal clamped up to min_interval.
    ep2 = intel.create_episode(deploy_event(2))["episode_id"]
    intel.open_checkpoint(ep2, "C+0", "s3")
    r = intel.record(ep2, "C+0", [], "insufficient-evidence", "s", "r", [], [],
                     next_check_proposal_minutes=1,
                     next_check_reason="high traffic: samples land in 60s")
    check("tightening proposal clamped up to min_interval",
          r["next_check_at"] == "+2m"
          and r["next_check"]["proposal"]["direction"] == "tighten")

    # 4c. In-bounds proposal honored verbatim.
    intel.open_checkpoint(ep2, "C+10", "s4")
    r = intel.record(ep2, "C+10", [], "insufficient-evidence", "s", "r", [], [],
                     next_check_proposal_minutes=12, next_check_reason="evidence-based")
    check("in-bounds proposal honored verbatim",
          r["next_check_at"] == "+12m" and not r["next_check"]["proposal"]["clamped"])

    # 5. Final stage: a proposal cannot extend the ladder.
    intel.open_checkpoint(ep2, "C+45", "s5")
    r = intel.record(ep2, "C+45", [], "insufficient-evidence", "s", "r", [], [],
                     next_check_proposal_minutes=10, next_check_reason="please continue")
    check("final stage: proposal cannot extend the ladder",
          r["next_check_at"] is None
          and r["next_check"]["proposal"]["result"] == "ignored_ladder_ended"
          and r["next_check"]["ladder_end"] == "final_stage")

    # 6. Exit criteria close the ladder early (needs healthy verdicts ->
    #    stub the policy evaluation to pass; rules: [] would otherwise
    #    evaluate insufficient and the recorder would reject healthy).
    real_evaluate = svc.evaluate
    svc.evaluate = lambda pack, stage, envs: {
        "policy_status": "pass", "policy_version": pack.version, "stage": stage,
        "rule_results": [], "required_missing": [],
        "unverified_observations": []}
    try:
        ep3 = intel.create_episode(deploy_event(3))["episode_id"]
        intel.open_checkpoint(ep3, "C+0", "s6")
        r1 = intel.record(ep3, "C+0", [], "healthy", "s", "r", [], [])
        intel.open_checkpoint(ep3, "C+10", "s7")
        r2 = intel.record(ep3, "C+10", [], "healthy", "s", "r", [], [],
                          next_check_proposal_minutes=10, next_check_reason="x")
        check("exit criteria: soak not met keeps the ladder open",
              r1["next_check_at"] == "+10m")
        check("exit criteria: 2 consecutive healthy + soak close the ladder",
              r2["next_check_at"] is None
              and r2["next_check"]["ladder_end"] == "exit_criteria"
              and r2["next_check"]["proposal"]["result"] == "ignored_ladder_ended")
    finally:
        svc.evaluate = real_evaluate

    # 6b. Every next_check decision is in the audit trail.
    from sqlalchemy import select
    from rollout_intel.models import Decision
    with intel.db.session() as s:
        vals = [json.loads(v) for v in s.execute(
            select(Decision.value_json).where(Decision.kind == "next_check")
        ).scalars()]
    check("all next_check decisions audited (7 records -> 7 rows)",
          len(vals) == 7 and all("source" in v for v in vals)
          and any(v.get("proposal", {}).get("clamped") for v in vals))

    print()
    print("all checks passed" if fails == 0 else f"{fails} check(s) FAILED")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
