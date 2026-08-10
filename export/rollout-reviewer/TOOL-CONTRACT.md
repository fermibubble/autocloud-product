# Tool contract — the surface the skill executes against

Two servers. Endpoints: **rollout-intel** MCP `http://host:7610/mcp`,
REST `http://host:7611`; **gcp-observe** MCP `http://host:7600/mcp`,
bundle face `http://host:7601`. Transport for MCP is streamable-http;
`examples/driver/session_driver.py` is a complete working client
(python `mcp` package). Full real payloads for every tool are in
`examples/trace.jsonl` and `examples/gather-output.txt` — the shapes
below are summaries of those actual results, not idealizations.

## If your harness does not speak MCP

Options, in order of effort:
1. **Bridge**: keep the servers as-is; expose each tool to your model
   through your own function-calling layer that forwards to MCP the way
   `examples/driver` does (~40 lines).
2. **REST-partial**: `run_stage_checks`-equivalent evidence is also
   available as plain HTTP (`GET :7601/observe/bundle`), and everything
   under `:7611/intel/*` is plain REST — but `record_checkpoint`,
   `get_context_pack`, and `run_stage_checks` (the policy-evaluating
   core) exist only as MCP tools; bridging them is required either way.
3. **Reimplement**: match the signatures below exactly; the skill's
   text names these tools verbatim.

**Minimum viable surface for the skill**: `get_context_pack`,
`run_stage_checks`, `record_checkpoint` (rollout-intel) +
`query_metric`, `search_logs` (gcp-observe), plus file read/write in
the agent workspace. The rest enrich but are optional.

## rollout-intel tools (MCP :7610/mcp)

### begin_review(trigger_json, session_id="")
Entry point for event-driven harnesses (session input is a raw trigger,
not header lines). `trigger_json` is the session input VERBATIM: a
platform audit-log entry, or a deferred_check notice
`{"type": "deferred_check", "unique_id": ...}`. Server-side
(`rollout_intel/triggers.py`): identity is derived from
platform-authoritative fields only; the episode id derives from the
event's `insertId` (`ep_<sha256(ref)[:16]>`, or a deterministic
synthesized ref for bare entries without one), so redelivered events
and duplicate timers dedupe onto one episode; the due checkpoint (first
ladder stage without a completed record) is opened idempotently — but
never after the ladder has ended, and never before the prior stage's
decided delay has elapsed (a not-before gate absorbs duplicate/early
timers: `not_due` + `seconds_remaining` says re-arm exactly that and
end the session). Returns:
```
{ status: review_due|not_due|ladder_complete|closed,
  episode_id, stage,            # stage null unless review_due
  checkpoint_id?,               # review_due only
  seconds_remaining?,           # not_due only
  unique_id,                    # the correlation id to arm defers with
  service, service_uid, identity_status: confirmed|candidate,
  episode_status, deduplicated: bool,
  prior_checkpoints: [{stage, stage_verdict, policy_status}], note }
```
Errors: unparseable trigger (no service derivable — never guessed; a
non-zero `protoPayload.status.code` also refuses — failed operations
deploy nothing), a deferred_check whose `unique_id` matches no episode
on this store, or a `correlation collision` (same insertId, different
parsed service — distinct events sharing a ref never silently merge).

### get_context_pack(episode_id, stage="")
What is known before evidence. Returns:
```
{ episode:  {episode_id, service_uid, revision_from/to, fingerprint{...}, status},
  identity: {status: confirmed|candidate, source, owner, note},
  policy:   {version, hard_rules_summary: [str]},
  checkpoint_schedule: {ladder: [{stage, offset_minutes}],
                        bounds: {min_interval_minutes, max_interval_minutes},
                        exit: {consecutive_healthy, min_soak_minutes},
                        outcome_horizons: [str], note},
  prior_checkpoints: [{stage, stage_verdict, policy_status, ...}],
  dossier:  {claims: [...], note},
  precedents: {scope_rung, healthy: [...], unhealthy: [...],
               insufficient_precedent: bool, note},
  generated_at }
```
Side effect: the read is journaled to `retrieval_audit`.

### run_stage_checks(episode_or_service, stage)
Collects the standard signed evidence bundle server-side (from
gcp-observe's bundle face), verifies every envelope's HMAC signature,
evaluates the deterministic policy, and caches the envelopes for
recording. Returns:
```
{ policy_status: pass|fail|insufficient_evidence, policy_version, stage,
  rule_results: [{rule_id, status: pass|fail|insufficient,
                  observed, threshold, observation_ids: [obs-*], note}],
  required_missing: [], unverified_observations: [],
  episode_id,
  observations: [{observation_id, type, quality{...}, summary}] }
```

### record_checkpoint(episode_or_service, stage, stage_verdict, reasoning_summary, report_md, observations="[]", precedent_episode_ids="[]", dossier_fields_used="[]", next_check_proposal_minutes=0, next_check_reason="")
THE single write door. `stage_verdict` must be one of
`healthy | regression-suspected | insufficient-evidence`. Evidence
defaults to the bundle cached by `run_stage_checks`; passing
`observations` (a JSON array of full envelopes) replaces it.
`reasoning_summary` is truncated at 2000 chars.
`next_check_proposal_minutes` > 0 PROPOSES the next check time:
tightening is honored down to the policy's `min_interval_minutes`,
loosening is clamped to `max_interval_minutes`, ending the ladder is
never a proposal (only policy exit criteria / the final stage /
governed windows close it). Units: minutes are the POLICY vocabulary
(ladders, bounds, soak — all floats, so `0.5` = 30s when a policy
wants sub-minute cadence); the response's `next_check.delay_seconds`
is the EXECUTION unit a deferral tool arms with — no conversion on the
agent side. The proposal, its clamped result, and the
reason are stored as a `next_check` audit decision. Server-side
guards, in order:
- envelope signature verification; foreign-service scope → error
  `scope_mismatch: ...`
- policy re-run; softening verdict (healthy vs fail/insufficient, or
  insufficient-evidence vs fail) → error `policy_conflict: ...` — the
  attempt is stored as an audit decision, the checkpoint stays open
- tightening (regression-suspected vs pass) is accepted
- replay-safe: already-completed checkpoint → `conflict: ... this
  attempt changed nothing`

Success:
```
{ checkpoint_id, policy_status, report_version, next_check_at,
  next_check: {next_check_at, minutes, delay_seconds, unique_id,
               source: ladder|proposal, default_minutes,
               ladder_end?: final_stage|exit_criteria|governed_window,
               proposal?: {proposal_minutes, clamped_minutes, clamped,
                           direction: tighten|loosen, reason}},
  policy: {…the re-run result…} }
```
The clock layer schedules the next session from `next_check_at`; null
means the ladder is closed (`next_check.ladder_end` says why). On a
defer-tool harness the agent arms
`defer_verification(next_check.unique_id, next_check.delay_seconds)` as
its last action — both values recorder-returned verbatim (never derived
from the event body), nothing when null (AGENT-CONTRACT §4 variant B).

### evaluate_policy(stage, observations)
Pure policy evaluation over an explicit envelope array (no recording,
no cache). Useful for what-if checks on extra evidence.

### find_similar_episodes(...) / get_dossier(service, as_of="") / propose_dossier_update(service, field, value_json, epistemic_type, rationale, valid_to="", source_episode_ids="[]")
Precedents (labeled-only, balanced, `insufficient_precedent` flag),
governed memory reads, and proposals. Agent proposals accept only
`epistemic_type` of `hypothesized|asserted` and never go live without
human promotion. All reads journaled.

## gcp-observe tools (MCP :7600/mcp)

`query_metric`, `search_logs`, `list_services`, `list_assets`,
`get_recommendations` — read-only; every result is a **signed
observation envelope**:
```
{ observation_id: "obs-<12hex>", type: metric_window|log_scan|workload_state|...,
  scope: {project, region, service}, observed_at, fresh_until (+10m),
  source: "gcp-observe", payload: {…tool-specific…},
  quality: {completeness, entry_count|sample_count, window_minutes},
  content_hash: "sha256:…", sig: "<hmac>" }
```
Envelopes are the only evidence rollout-intel will accept: unsigned or
stale (past `fresh_until`) satisfies nothing; edited payloads break
`content_hash`. Signing key: `OBS_SIGNING_KEY` (see README security
notes).

## REST fallbacks (rollout-intel :7611, plain HTTP/JSON)

| Method + path | Purpose |
|---|---|
| GET `/intel/health` | liveness + policy version |
| GET `/intel/episodes[?status=]` | list episodes |
| GET `/intel/episodes/{id}` | episode + checkpoints (incl. `report_md`) + observation rows (`sig_verified`) — what the validator consumes |
| POST `/intel/episodes` | create an episode from a deploy event (see AGENT-CONTRACT §4) |
| POST `/intel/triggers[?session_id=]` | `begin_review` for harness drivers: body = the raw trigger event, verbatim |
| GET `/intel/episodes/by-ref?ref=` | episode by trigger correlation id (insertId / deferred unique_id) |
| POST `/intel/flush` | quiesce + merge the WAL so intel.db alone is the complete store (session-DB harnesses; 409 while another process holds it) |
| POST `/intel/episodes/{id}/checkpoints` | open a checkpoint `{stage, session_id}` |
| POST `/intel/episodes/{id}/outcome` | record outcome horizon / final label (never overwrites an existing label) |
| GET `/intel/precedents?episode=` · GET `/intel/dossier?service=[&as_of=]` · GET `/intel/dossier/journal` · `/intel/dossier/proposals` | retrieval + memory reads |
| POST `/intel/dossier/propose` · `/intel/feedback` | operator-side writes |
| GET `/intel/metrics/decision-quality` · `/intel/learning/*` | falseSafe/falseHalt over labeled episodes; conservative learning suggestions |
| POST `/intel/fixtures/load` · `/intel/replay/reset` | test-only: arm eval fixtures / reset the store |

gcp-observe REST: GET `:7601/observe/bundle?service=<name>&stage=<T+N>`
returns the standard bundle as a JSON array of envelopes (this is what
`run_stage_checks` fetches server-side).

## Error vocabulary your harness may surface to the model

`policy_conflict` (softening rejected — reconcile and re-record) ·
`scope_mismatch` (foreign-service evidence) · `conflict` (checkpoint
already recorded; idempotent no-op) · `unknown episode/service` ·
envelope verification failures land in `unverified_observations` and
per-rule `insufficient` statuses rather than exceptions.
