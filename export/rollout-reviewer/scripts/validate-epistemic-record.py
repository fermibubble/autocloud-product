#!/usr/bin/env python3
"""Validate the epistemic record embedded in a rollout checkpoint report.

The record is the skill-side convention that implements P1 of the Rollout
Reviewer standard: a fenced yaml block between the exact markers

    <!-- epistemic-record:begin -->
    ```yaml
    ...
    ```
    <!-- epistemic-record:end -->

This validator enforces the convention where the recorder deliberately does
not (report_md is stored unvalidated - see docs/product/rollout-reviewer.md,
gap G1): exactly one record per report, schema-valid, internally
cross-referenced, consistent with the recorded verdict.

Usage:
  validate-epistemic-record.py REPORT.md            # a report file ('-' = stdin)
  validate-epistemic-record.py --episode fx_ep_001 --intel http://127.0.0.1:7610
                                                    # validate every completed
                                                    # checkpoint's report_md
  validate-epistemic-record.py --self-test          # validate the worked
                                                    # examples in the skill
                                                    # playbook against the schema

Options:
  --schema PATH               (default: schemas/epistemic-record.schema.json)
  --session-obs FILE          JSON array of envelope observation_ids; every
                              obs-* evidence_ref must be in this set
  --episode ID --intel URL    fetch checkpoints + observation ids over REST
  --stage STAGE               with --episode: only this checkpoint
  --require-quoted-evidence   fail unless the record quarantines at least one
                              possible-prompt-injection quoted_evidence entry
  --json                      machine-readable result on stdout

Exit codes:
  0 valid | 2 wrong number of record blocks | 3 yaml parse error
  4 schema violation | 5 cross-reference failure | 6 quoted-evidence required
  and missing | 7 environment/usage error

Run with: uv run --with pyyaml --with jsonschema scripts/validate-epistemic-record.py ...
(or any python with pyyaml + jsonschema installed).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("error: pyyaml not installed - run via: uv run --with pyyaml --with jsonschema", file=sys.stderr)
    sys.exit(7)
try:
    import jsonschema
except ImportError:  # pragma: no cover
    print("error: jsonschema not installed - run via: uv run --with pyyaml --with jsonschema", file=sys.stderr)
    sys.exit(7)

EXPORT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = EXPORT_ROOT / "schemas" / "epistemic-record.schema.json"
PLAYBOOK = EXPORT_ROOT / "skill" / "trustworthy-rollout-review" / "references" / "epistemics.md"

BLOCK_RE = re.compile(
    r"<!--\s*epistemic-record:begin\s*-->\s*```(?:yaml|yml)?\s*\n(.*?)```\s*<!--\s*epistemic-record:end\s*-->",
    re.DOTALL,
)
# Headline verdict outside the record block, e.g. "Verdict: regression-suspected"
# or the list form "- Verdict: healthy".
HEADLINE_RE = re.compile(
    r"(?im)^[ \t>*-]*\**\s*verdict\s*\**\s*[:*]\s*`?(healthy|regression-suspected|insufficient[-_ ]evidence)`?"
)


_SCHEMA_DIR = DEFAULT_SCHEMA.parent


def _make_registry():
    """File-based $ref resolver rooted at the schemas directory.

    The record schema composes its sub-schemas (evidence-ref,
    quoted-evidence, proposed-action, validity-horizon) by relative
    $ref; this registry retrieves them from disk on demand.
    """
    from referencing import Registry, Resource  # ships with jsonschema>=4.18

    def retrieve(uri: str):
        path = _SCHEMA_DIR / uri
        if not path.is_file():
            raise LookupError(f"unresolvable schema $ref: {uri}")
        return Resource.from_contents(json.loads(path.read_text()))

    return Registry(retrieve=retrieve)


def load_schema(path: Path) -> dict:
    global _SCHEMA_DIR
    _SCHEMA_DIR = path.resolve().parent
    return json.loads(path.read_text())


def extract_blocks(report_text: str) -> list[str]:
    return [m.group(1) for m in BLOCK_RE.finditer(report_text)]


def validate_record_text(block: str, schema: dict) -> tuple[int, dict | None, list[str]]:
    """Parse + schema-validate one record block. Returns (exit_code, record, errors)."""
    try:
        record = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        return 3, None, [f"yaml parse error: {exc}"]
    if not isinstance(record, dict):
        return 3, None, ["record did not parse to a mapping"]
    validator = jsonschema.Draft7Validator(schema, registry=_make_registry())
    errors = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = [f"schema: {'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
        return 4, record, msgs
    return 0, record, []


def cross_check(
    record: dict,
    report_text: str | None,
    session_obs: set[str] | None,
    recorded_verdict: str | None,
) -> list[str]:
    """Reference checks the schema alone cannot express. Returns error strings."""
    errs: list[str] = []
    local_ids = {o["id"] for o in record.get("observations", [])}
    for inf in record.get("inferences", []):
        for ref in inf.get("supported_by", []):
            if ref not in local_ids:
                errs.append(f"cross-ref: supported_by cites '{ref}' but no observation has that id")
    if session_obs is not None:
        for obs in record.get("observations", []):
            for ref in obs.get("evidence_refs", []):
                if ref.startswith("obs-") and ref not in session_obs:
                    errs.append(f"cross-ref: evidence_ref '{ref}' not among the session's envelope ids")
    if recorded_verdict is not None and record.get("verdict") != recorded_verdict:
        errs.append(
            f"cross-ref: record verdict '{record.get('verdict')}' != recorded stage_verdict '{recorded_verdict}'"
        )
    if report_text is not None:
        stripped = BLOCK_RE.sub("", report_text)
        m = HEADLINE_RE.search(stripped)
        if m:
            headline = m.group(1).lower().replace("_", "-").replace(" ", "-")
            if headline != record.get("verdict"):
                errs.append(
                    f"cross-ref: report headline verdict '{headline}' != record verdict '{record.get('verdict')}'"
                )
    return errs


def check_quoted_evidence(record: dict) -> list[str]:
    entries = record.get("quoted_evidence") or []
    for entry in entries:
        if "possible-prompt-injection" in entry.get("flags", []):
            return []
    return ["quoted-evidence: no entry flagged possible-prompt-injection, but one was required"]


def validate_report(
    report_text: str,
    schema: dict,
    session_obs: set[str] | None,
    recorded_verdict: str | None,
    require_quoted: bool,
) -> tuple[int, dict]:
    result: dict = {"blocks": 0, "errors": []}
    blocks = extract_blocks(report_text)
    result["blocks"] = len(blocks)
    if len(blocks) != 1:
        result["errors"].append(f"expected exactly 1 epistemic-record block, found {len(blocks)}")
        return 2, result
    code, record, errors = validate_record_text(blocks[0], schema)
    result["errors"].extend(errors)
    if code != 0:
        return code, result
    xerrs = cross_check(record, report_text, session_obs, recorded_verdict)
    if xerrs:
        result["errors"].extend(xerrs)
        return 5, result
    if require_quoted:
        qerrs = check_quoted_evidence(record)
        if qerrs:
            result["errors"].extend(qerrs)
            return 6, result
    result["verdict"] = record.get("verdict")
    return 0, result


def fetch_episode(intel: str, episode_id: str) -> dict:
    url = f"{intel.rstrip('/')}/intel/episodes/{episode_id}"
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - operator-supplied URL
        return json.loads(resp.read())


def episode_obs_ids(episode: dict) -> set[str] | None:
    rows = episode.get("observations")
    if not isinstance(rows, list):
        return None  # endpoint variant without observation rows - skip that check
    ids = {r.get("observation_id") for r in rows if isinstance(r, dict) and r.get("observation_id")}
    return ids or None


def run_self_test(schema: dict) -> int:
    """Every marker block in the skill playbook must be schema-valid (drift guard)."""
    if not PLAYBOOK.exists():
        print(f"self-test: playbook not found at {PLAYBOOK}", file=sys.stderr)
        return 7
    blocks = extract_blocks(PLAYBOOK.read_text())
    if not blocks:
        print("self-test: no epistemic-record blocks found in the playbook", file=sys.stderr)
        return 2
    worst = 0
    for i, block in enumerate(blocks, 1):
        code, record, errors = validate_record_text(block, schema)
        if code == 0:
            xerrs = cross_check(record, None, None, None)
            if xerrs:
                code, errors = 5, xerrs
        status = "ok" if code == 0 else "FAIL"
        print(f"self-test: example {i}/{len(blocks)}: {status}")
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        worst = max(worst, code)
    return worst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", nargs="?", help="report file path, or '-' for stdin")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    ap.add_argument("--session-obs", help="JSON file: array of envelope observation_ids")
    ap.add_argument("--episode", help="episode id to validate over REST")
    ap.add_argument("--intel", default="http://127.0.0.1:7611", help="rollout-intel REST base URL")
    ap.add_argument("--stage", help="with --episode: only this checkpoint stage")
    ap.add_argument("--require-quoted-evidence", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    schema = load_schema(Path(args.schema))

    if args.self_test:
        return run_self_test(schema)

    session_obs: set[str] | None = None
    if args.session_obs:
        session_obs = set(json.loads(Path(args.session_obs).read_text()))

    results: list[dict] = []
    worst = 0

    if args.episode:
        try:
            episode = fetch_episode(args.intel, args.episode)
        except Exception as exc:  # noqa: BLE001
            print(f"error: could not fetch episode {args.episode}: {exc}", file=sys.stderr)
            return 7
        if session_obs is None:
            session_obs = episode_obs_ids(episode)
        checkpoints = [
            c for c in episode.get("checkpoints", [])
            if c.get("completed_at") and (not args.stage or c.get("stage") == args.stage)
        ]
        if not checkpoints:
            print(f"error: no completed checkpoints for {args.episode}", file=sys.stderr)
            return 7
        for cp in checkpoints:
            code, res = validate_report(
                cp.get("report_md") or "",
                schema,
                session_obs,
                cp.get("stage_verdict"),
                args.require_quoted_evidence,
            )
            res.update({"episode": args.episode, "stage": cp.get("stage"), "exit": code})
            results.append(res)
            worst = max(worst, code)
    else:
        if not args.report:
            ap.error("provide a report file, --episode, or --self-test")
        text = sys.stdin.read() if args.report == "-" else Path(args.report).read_text()
        code, res = validate_report(text, schema, session_obs, None, args.require_quoted_evidence)
        res["exit"] = code
        results.append(res)
        worst = code

    if args.as_json:
        print(json.dumps({"results": results, "exit": worst}, indent=2))
    else:
        for res in results:
            where = f"{res.get('episode', args.report or '-')}:{res.get('stage', '')}".rstrip(":")
            if res["exit"] == 0:
                print(f"ok: {where} - record valid (verdict={res.get('verdict')})")
            else:
                print(f"FAIL({res['exit']}): {where}")
                for e in res["errors"]:
                    print(f"  - {e}", file=sys.stderr)
    return worst


if __name__ == "__main__":
    sys.exit(main())
