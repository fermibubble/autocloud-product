#!/usr/bin/env python3
"""intelctl: the human side of the dossier governance loop.

Agents may only PROPOSE dossier facts (hypothesized/asserted); this tool
is how an operator reviews, promotes (optionally upgrading the epistemic
type to observed/approved), rejects, and re-syncs the harness projection.

  intelctl.py dossier list --service demo-healthy [--as-of 2026-07-01T00:00:00Z]
  intelctl.py dossier journal [--service demo-healthy]
  intelctl.py proposals
  intelctl.py propose --service demo-healthy --field p99_baseline_ms \
      --value 185 --type observed --rationale "30d p99 plateau" [--expires ...]
  intelctl.py promote <rev_id> [--as observed] [--by sre-name]
  intelctl.py reject <rev_id> [--by sre-name]
  intelctl.py sync

Env: INTEL_API (default http://127.0.0.1:7611).
"""

import argparse
import json
import os
import sys
import urllib.request

API = os.environ.get("INTEL_API", "http://127.0.0.1:7611")


def call(path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data,
                                 method="POST" if data is not None else "GET")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"error {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)


def show(obj) -> None:
    print(json.dumps(obj, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(prog="intelctl")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dossier")
    dsub = d.add_subparsers(dest="dcmd", required=True)
    dl = dsub.add_parser("list")
    dl.add_argument("--service", required=True)
    dl.add_argument("--as-of", dest="as_of", default="")
    dj = dsub.add_parser("journal")
    dj.add_argument("--service", default="")

    sub.add_parser("proposals")

    pp = sub.add_parser("propose")
    pp.add_argument("--service", required=True)
    pp.add_argument("--field", required=True)
    pp.add_argument("--value", required=True, help="JSON value (bare strings ok)")
    pp.add_argument("--type", required=True, dest="etype")
    pp.add_argument("--rationale", default="")
    pp.add_argument("--confidence", type=float, default=None)
    pp.add_argument("--expires", default=None)

    pr = sub.add_parser("promote")
    pr.add_argument("rev_id")
    pr.add_argument("--as", dest="as_type", default=None,
                    help="upgrade epistemic type on promotion (e.g. observed)")
    pr.add_argument("--by", default="operator")

    rj = sub.add_parser("reject")
    rj.add_argument("rev_id")
    rj.add_argument("--by", default="operator")

    sub.add_parser("sync")
    sub.add_parser("suggestions")
    sub.add_parser("signal-utility")

    args = ap.parse_args()
    if args.cmd == "dossier" and args.dcmd == "list":
        q = f"/intel/dossier?service={args.service}"
        if args.as_of:
            q += f"&as_of={args.as_of}"
        show(call(q))
    elif args.cmd == "dossier" and args.dcmd == "journal":
        q = "/intel/dossier/journal"
        if args.service:
            q += f"?service={args.service}"
        show(call(q))
    elif args.cmd == "proposals":
        show(call("/intel/dossier/proposals"))
    elif args.cmd == "propose":
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        show(call("/intel/dossier/propose", {
            "service": args.service, "field": args.field, "value": value,
            "epistemic_type": args.etype, "rationale": args.rationale,
            "confidence": args.confidence, "expires_at": args.expires}))
    elif args.cmd == "promote":
        show(call(f"/intel/dossier/{args.rev_id}/promote",
                  {"verified_by": args.by, "epistemic_type": args.as_type}))
    elif args.cmd == "reject":
        show(call(f"/intel/dossier/{args.rev_id}/reject", {"actor": args.by}))
    elif args.cmd == "sync":
        show(call("/intel/dossier/sync", {}))
    elif args.cmd == "suggestions":
        show(call("/intel/learning/suggestions"))
    elif args.cmd == "signal-utility":
        show(call("/intel/learning/signal-utility"))


if __name__ == "__main__":
    main()
