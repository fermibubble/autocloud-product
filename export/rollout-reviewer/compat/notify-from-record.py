#!/usr/bin/env python3
"""Render legacy-format chat notifications FROM the recorded episode.

Reproduces the legacy rollout-review skill's three milestone message
formats (Rollout Initiated / Issue Detected / Completed Successfully),
but sourced from the episode store instead of free agent prose - the
message is a projection of recorded truth, sent AFTER record_checkpoint.
Pipe stdout to your chat tool (e.g. send_google_chat_message).

Usage:
  notify-from-record.py --episode fx_eval_b_06 [--intel http://127.0.0.1:7611]
                        [--milestone auto|initiated|issue|success]
  notify-from-record.py --from-file episode-state.json   # offline / testing

Milestone 'auto': initiated if no checkpoint completed yet; issue if the
latest verdict is regression-suspected; success if T+30 completed
healthy; otherwise a progress update. The script REFUSES to render
'success' when the record does not support it - a notification may
never outrun the recorder.

Requires pyyaml (run via: uv run --project ../servers/rollout-intel python ...).
"""
import argparse
import json
import re
import sys
import urllib.request

import yaml

RECORD_RE = re.compile(
    r"<!--\s*epistemic-record:begin\s*-->\s*```(?:yaml|yml)?\s*\n(.*?)```\s*<!--\s*epistemic-record:end\s*-->",
    re.DOTALL,
)


def load_episode(args) -> dict:
    if args.from_file:
        return json.loads(open(args.from_file).read())
    url = f"{args.intel.rstrip('/')}/intel/episodes/{args.episode}"
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read())


def parse_record(report_md: str) -> dict:
    m = RECORD_RE.search(report_md or "")
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def service_name(ep: dict) -> str:
    uid = ep.get("service_uid", "")
    parts = uid.split("/")
    return parts[-3] if len(parts) >= 3 else uid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode")
    ap.add_argument("--intel", default="http://127.0.0.1:7611")
    ap.add_argument("--from-file")
    ap.add_argument("--milestone", default="auto",
                    choices=["auto", "initiated", "issue", "success"])
    args = ap.parse_args()
    if not (args.episode or args.from_file):
        ap.error("provide --episode or --from-file")

    ep = load_episode(args)
    svc = service_name(ep)
    env = ep.get("service_uid", "").split("/")[-2] if ep.get("service_uid") else "?"
    done = [c for c in ep.get("checkpoints", []) if c.get("completed_at")]
    done.sort(key=lambda c: c.get("completed_at") or "")
    latest = done[-1] if done else None
    record = parse_record(latest.get("report_md", "")) if latest else {}
    verdict = latest.get("stage_verdict") if latest else None

    milestone = args.milestone
    if milestone == "auto":
        if latest is None:
            milestone = "initiated"
        elif verdict == "regression-suspected":
            milestone = "issue"
        elif verdict == "healthy" and latest.get("stage") == "T+30":
            milestone = "success"
        else:
            milestone = "progress"

    # A notification may never outrun the recorder.
    if milestone == "success" and not (verdict == "healthy" and latest and latest.get("stage") == "T+30"):
        print("refusing to render 'success': the record does not show a healthy T+30", file=sys.stderr)
        return 2
    if milestone == "issue" and verdict != "regression-suspected":
        print("refusing to render 'issue': latest recorded verdict is not regression-suspected", file=sys.stderr)
        return 2

    conf = record.get("confidence", {}) or {}
    checks_line = "; ".join(
        f"{c['stage']}: {c['stage_verdict']}({c['policy_status']})" for c in done) or "none yet"

    if milestone == "initiated":
        print(f"""🔎 *Rollout Analysis Initiated*
*Service*: `{svc}`  *Environment*: `{env}`
*Target Version*: `{ep.get('revision_to', '?')}`  *Baseline Version*: `{ep.get('revision_from', '?')}`
*Status*: Watching & Analyzing (episode `{ep.get('episode_id')}`)
*Checkpoints*: T+0 / T+5 / T+15 / T+30 - each ends in a recorded, evidence-backed verdict.""")
    elif milestone == "issue":
        unknowns = record.get("unknowns", [])
        symptoms = "\n".join(f"  - {o['statement']}" for o in record.get("observations", [])
                             if any(str(r).startswith("policy:") for r in o.get("evidence_refs", []))) or "  - see recorded report"
        action = record.get("proposed_action") or {}
        remediation = (f"*Proposed remediation (draft - requires {', '.join(action.get('approval_required_from', ['approval']))})*: "
                       f"{action.get('action')}" if action else
                       "*Proposed remediation*: none drafted; see recorded report")
        print(f"""⚠️ *Rollout Issue Detected*
*Service*: `{svc}`  *Environment*: `{env}`  *Target Version*: `{ep.get('revision_to', '?')}`
*Status*: ❌ regression-suspected at {latest['stage']} (recorded {latest['completed_at']})
*Confidence*: {conf.get('level', '?')} - {conf.get('basis', 'see record')}
*Symptoms (from recorded evidence)*:
{symptoms}
*Unknowns*: {len(unknowns)} recorded
{remediation}
*Full evidence*: episode `{ep.get('episode_id')}`, report_version {latest.get('report_version')}""")
    elif milestone == "success":
        print(f"""✅ *Rollout Review Completed Successfully*
*Service*: `{svc}`  *Environment*: `{env}`  *Target Version*: `{ep.get('revision_to', '?')}`
*Status*: healthy through the full checkpoint ladder
*Checkpoints*: {checks_line}
*Confidence*: {conf.get('level', '?')} - {conf.get('basis', 'see record')}
*Valid through*: {record.get('valid_through', '?')} (reassess if: {record.get('reassess_if', '?')})
*Note*: outcome labels at 30m/2h/24h will independently grade this verdict.""")
    else:  # progress
        print(f"""📋 *Rollout Review Progress*
*Service*: `{svc}`  *Episode*: `{ep.get('episode_id')}`
*Checkpoints so far*: {checks_line}
*Latest verdict*: {verdict or 'none'} - see recorded report for the epistemic record.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
