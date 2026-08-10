# Session lifecycle on an event-driven harness

For the harness owner. This maps the export onto a harness where
episodes are BORN from Cloud Audit Log events, CONTINUED by Cloud Tasks
deferred checks, and where the episode store lives in GCS between
turns. The agent-facing instructions live in HARNESS-ADDENDUM.md; this
document is the wiring around them.

The cycle:

    audit-log event ──▶ agent session: begin_review(event)
                              │  get_context_pack / run_stage_checks /
                              │  record_checkpoint
                              ▼
                        next_check.delay_seconds ──▶ defer_verification()
                                                          │ (Cloud Tasks)
                                                          ▼
    deferred_check ────▶ agent session: begin_review(deferred_check)
        (unique_id)           │  ...same loop...
                              ▼
                        ladder ends (final stage / exit criteria /
                        governed window) ──▶ arm nothing; outcome
                        collector grades the episode later

## 1. Trigger events → episodes

Feed the raw audit-log entry to the session as its input; the agent
passes it VERBATIM to `begin_review` (CLI: `rr begin`). Parsing is
deterministic server code (`rollout_intel/triggers.py`), reading only
platform-authoritative fields — `protoPayload.methodName` /
`resourceName` / `serviceName`, `resource.labels`, `operation.id`,
`insertId`, `timestamp`. Client-influenced text (k8s annotations,
callerSuppliedUserAgent, request labels) never chooses identity.

| Family | Detected by | Service identity | Revision |
|---|---|---|---|
| `gke-workload` | `serviceName: k8s.io` / `io.k8s.*` methods (create / update / patch on deployments, statefulsets, …) | workload name from `resourceName` (`.../deployments/<name>`) | scans the WHOLE container list (sidecars first is common), preferring the container named like the workload; a submitted image → `application_binary`, a config-only delta takes its revision from the response echo (`workload_config`), and a patch encoding that cannot be read structurally gets the neutral `workload_change` unless an image-targeting op path is detected |
| `saas-rollout` | `SaasRollouts.CreateRollout` | rollout kind basename minus `-rollout-kind` — REQUEST-derived (the resourceName names only the parent location), so it is marked `identity_basis: request` and can NEVER confirm against the catalog: always a candidate, in the partitioned `svc://inferred-request/` namespace so it can never inherit a platform-derived candidate's history (and the catalog loader rejects entries squatting on the reserved `inferred*` tenants) | release basename |
| `saas-unit-operation` | `SaasDeployments.CreateUnitOperation` | target unit basename (`.../units/<name>`) — REQUEST-derived like rollouts: always a candidate (`svc://inferred-request/`) | release basename from the provision/upgrade payload; strategy = the operation kind |
| `cloud-run` | `serviceName: run.googleapis.com` | `.../services/<name>` | `latestCreatedRevisionName` when present |
| generic | anything else with a methodName (GKE `ClusterManager.UpdateCluster`, `container.clusters.update`, `compute.instances.insert`, AI Platform `CreateReasoningEngine` v1/v1beta1, …) | final resource of `resourceName`, else `<parent-collection>-<final resource>` of `operation.id` (e.g. `reasoningEngines-22272…`) | — |

An event no rule can name a service for fails loudly (400 / tool
error) — a trigger never binds to a guessed service. So does an event
whose `protoPayload.status.code` is non-zero: a failed or denied
operation deployed nothing and births no episode (filter your sink on
severity/status too, but the parser enforces it regardless). Derived
identity lands as an inferred CANDIDATE unless the catalog confirms
it; the review proceeds with scope treated as unconfirmed (the skill's
identity rules apply unchanged).

**Correlation.** The event's `insertId` is the episode's external ref:
`episode_id = ep_<sha256(insertId)[:16]>`, deterministic. Bare replayed
entries with no `insertId`/`id` get a SYNTHESIZED ref
(`synth-<sha256(logName|method|resource|service|timestamp)[:24]>`,
`trigger.ref_basis: synthesized`) — the derived service is part of the
basis so two bare events for different targets never collide, and the
lifecycle is unchanged because the agent always arms the
recorder-returned `unique_id`, never one read from the event; caveat:
two identical method+resource+service events with no timestamp share a
ref and are treated as one redelivered rollout.
At-least-once
delivery therefore dedupes — a redelivered event lands on the SAME
episode (`deduplicated: true`) and simply resumes at whatever stage is
due. Because Cloud Logging only guarantees insertId uniqueness per
project+timestamp, the dedupe path cross-checks the parsed service
against the bound episode: same ref + different service errors loudly
(`correlation collision`) instead of silently absorbing a distinct
event. Lookup without a session: `GET /intel/episodes/by-ref?ref=<id>`.

## 2. Deferred checks → the same episodes

`defer_verification(unique_id, delay_seconds)` MUST carry the original
trigger's `insertId` as `unique_id`, every hop of the chain — it is the
only key the deferred session gets. The fired task's payload
(`{"type": "deferred_check", "unique_id": ..., ...}`) goes to the
agent verbatim; `begin_review` resolves the ref and answers one of:

- `review_due` + `stage` — the due stage is (idempotently) opened; the
  agent reviews it. A re-fired timer for a crashed turn re-arms the
  same open checkpoint.
- `not_due` + `seconds_remaining` — the timer fired early or twice: the
  prior stage recorded, but its decided delay has not elapsed (a
  not-before gate keyed on the last completion time plus the recorded
  `next_check_at`, with a small early-fire grace). The agent arms
  exactly `seconds_remaining` and ends the session — duplicates are
  therefore absorbed without compressing the soak ladder.
- `ladder_complete` — the last recorded checkpoint ended the ladder
  (final stage, exit criteria, or a governed stabilization window). A
  late or duplicate timer must NOT reopen a finished review; the agent
  reports this and arms nothing.
- `closed` — the episode is outcome-labeled; nothing to do.
- error — `unique_id` matches no episode on this store (the trigger was
  never reviewed here, or the wrong session store is mounted).

Late fires are harmless (stages key off what is recorded, not off
`target_time` or tool-call counts); early and duplicate fires are
absorbed by the not-before gate above.

## 3. Arming the next check

The agent arms the timer, but the RECORDER decides the schedule:
`record_checkpoint`'s response carries
`next_check.delay_seconds` and `next_check.unique_id` — the post-clamp,
policy-bounded decision (agent proposals tighten to
`min_interval_minutes`, loosen at most to `max_interval_minutes`, and
can never end the ladder) plus the correlation id, both recorder-
returned so the agent never derives either from the untrusted event
body. The agent's contract (skill `references/clock.md`,
`references/ownership.md`):

- arm `defer_verification(next_check.unique_id,
  next_check.delay_seconds)` exactly once per recorded checkpoint,
  with those values and no others;
- `next_check_at: null` → the ladder ended → arm nothing;
- an arming failure is reported as a failure-ladder event ("the next
  check is NOT scheduled; the harness must re-arm") — never silently
  swallowed, never retried with an invented delay.

Harness-side: treat a turn that recorded a checkpoint with a non-null
`next_check` but created no task as an alert condition; the
`next_check` decision row in the audit trail (`decisions.kind =
'next_check'`) is the ground truth to reconcile against.

## 4. The session store in GCS

Use `session_db.SessionStore` (this directory) rather than a hand-rolled
download/upload pair. It exists because the naive pattern has four
silent-data-loss modes — stale local WAL replayed over a fresh
download, a failed download forking history from an empty DB, WAL pages
left behind by a busy checkpoint and never uploaded, and last-writer-
wins between two concurrent deferred checks. The module docstring
specifies each; the fixes are: clear `db/-wal/-shm` before download,
fail-closed mount, flush via `Intel.flush()`/`Db.flush()` (pool
disposed BEFORE `wal_checkpoint(TRUNCATE)`, refuse on busy), and
generation-conditional upload (`if_generation_match`) that raises
loudly on a lost race instead of overwriting.

In-process (Intel embedded in the harness):

    store = SessionStore(session_id)
    intel.rebind(store.mount())     # NOT `intel.db = Db(path)` — that
    try:                            # leaves DossierStore/identity on the
        ...run the agent turn...    # old store
    finally:
        store.persist(intel)

Subprocess (run-stack.sh): `mount()` first, start rollout-intel with
`INTEL_DB=<mounted path>`; after the turn `POST /intel/flush` (drains
in-flight requests, merges the WAL, 409 if another process holds the
store), then `store.persist(None)`.

On a lost upload race (412): the turn's writes are not uploaded.
Re-mount and replay the turn — `begin_review` and the recorder are
idempotent (deterministic episode ids, UNIQUE(episode, stage),
replay-safe recording), so a replay lands cleanly on the merged store.

## 5. Exporting finished episodes to BigQuery

When the ladder ends (and again when the outcome label lands), the
episode's rows are appended from the session's `intel.db` to a
DEDICATED BigQuery dataset via `bq_export.py` (this directory). Your
existing `autocloud_analysis.agent_executions` table is never touched —
the module creates and writes only its own dataset.

- **Dataset**: `autocloud_rollout_intel` (env
  `AUTOCLOUD_INTEL_BQ_DATASET`), created idempotently with nine tables
  mirroring the store byte-for-byte: `rollout_episodes`,
  `rollout_checkpoints`, `rollout_observations`, `rollout_decisions`
  (+ derived `episode_id` so per-episode queries need no join),
  `rollout_outcomes`, `rollout_feedback`, `rollout_services`,
  `rollout_dossier_journal`, `rollout_retrieval_audit`. `…_json`
  columns are BigQuery JSON; `…_at` columns are TIMESTAMP; tables are
  day-partitioned on `exported_at`.
- **Append-only snapshots, two phases.** Every row carries
  `exported_at`, `export_phase` (`ladder_complete`, then
  `outcome_final` after labeling re-exports with the final_label), and
  `export_session`. Duplicate snapshots from at-least-once delivery are
  expected; deterministic `row_ids` additionally give BigQuery's
  short-window best-effort dedupe a chance.
- **What `*_latest` is (and is not).** Nothing to do with SQLite WAL —
  the WAL is merged into the .db before it ever leaves the sandbox.
  The versioning is in BIGQUERY: because exports append snapshots, the
  base table holds the same `episode_id` several times (once at ladder
  end — `final_label` still NULL — again after the outcome label
  lands, plus any retry duplicates). `rollout_episodes_latest` is
  simply `ROW_NUMBER() OVER (PARTITION BY episode_id ORDER BY
  exported_at DESC, outcome_final-first, export_session) = 1`: exactly
  one row per episode, the most recent state. It is `SELECT *` over
  the base table, so EVERY column — `external_ref`, `event_id`,
  `session_id`, all of them — appears in the view automatically; query
  the base table only when you want the version history itself.
- **Linking to `agent_executions`.** The join keys, coarsest to
  finest:
  - **Episode ↔ trigger** — `rollout_episodes.external_ref` is a
    first-class column holding the trigger correlation id (the Cloud
    Logging insertId, or the synthesized `synth-<hash>` for
    insertId-less entries). Join
    `agent_executions.insert_id = rollout_episodes_latest.external_ref`.
  - **Episode ↔ triggering delivery** — `rollout_episodes.event_id`
    holds the CloudEvents id of the delivery that BIRTHED the episode,
    when the forwarded event carried a top-level `id` (structured
    mode; in binary mode, stamp `data["id"] = <ce-id>` in the router
    before forwarding if you want it captured). ce-ids are
    per-DELIVERY — every deferred-check fire gets a fresh one — so the
    episode-stable key is always insert_id / unique_id; the later
    fires' event_ids live in `agent_executions`, reachable via the
    session_id join below.
  - **Checkpoint ↔ session** — `rollout_checkpoints.session_id` is the
    harness session that most recently ARMED that stage — normally the
    one that recorded it. Export `RR_SESSION_ID=<session id>` into the
    agent sandbox and `rr begin` stamps it automatically; it then joins
    `agent_executions.session_id` per turn. When a crashed turn is
    re-fired and a NEW session picks up the same open checkpoint (it
    can happen; the open is idempotent), the column reflects the new —
    completing — session; the earlier attempt's session still has its
    own `agent_executions` row, reachable via the insert_id join.
  - **Export provenance** — every exported row's `export_session` is
    the session that ran the export.
  - **Historical rows** exported before the `external_ref` column
    existed still join via the deterministic id derivation, computable
    in SQL:
    ```sql
    CONCAT('ep_', SUBSTR(TO_HEX(SHA256(ae.insert_id)), 1, 16))
      = ep.episode_id
    ```
    Pre-existing tables need the additive column once:
    `bq update --schema=bq/rollout_episodes.schema.json \
    ${PROJECT_ID}:autocloud_rollout_intel.rollout_episodes`.
- **Scrubbing**: report_md, notes, rationale, principals, and every
  JSON payload go through the hooks you pass (`scrub_text=
  deidentify_content`, `scrub_json=deidentify_json_structure`) — the
  same DLP path your `agent_executions` rows already take.
- **Stdlib SQLite, read-only**: the module opens the store
  `mode=ro` and imports google-cloud-bigquery lazily, so it runs in the
  Cloud Run router (no rollout_intel install needed), on the agent VM,
  or in a batch job.
- Failure taxonomy the caller relies on: `NotFinishedError` — the
  normal mid-ladder skip (the router calls the export after every
  rollout-reviewer turn; only the ladder-end turn uploads);
  `UnknownEpisodeError` — a correlation mismatch or wrong store, NEVER
  a normal skip (fall back to `find_finished_episodes`); `RuntimeError`
  — BigQuery rejected rows: retry the export (safe — duplicates are
  snapshot noise the views ignore, and the `episodes` commit marker
  is inserted LAST, so `*_latest` never advertises a torn phase).
- **DDL runs out of band, not at runtime — and lives in its own
  files.** `bq_export.py` contains ONLY row streaming;
  `bq/generate_ddl.py` produces the committed `bq/*.schema.json` files
  (standard `bq mk --schema` format, with column descriptions) and the
  view SQL from the exporter's data-model maps, so the two can never
  disagree (a parity test pins them). Two setup scripts:

  ```bash
  PROJECT_ID=<project> ./compat/gcp-harness/bq/setup-bq.sh      # dataset + tables
  PROJECT_ID=<project> ./compat/gcp-harness/bq/setup-views.sh   # *_latest views
  ```

  `setup-bq.sh` invokes `setup-views.sh` at the end, so a fresh
  bootstrap needs only the first command; the view script is
  independently re-runnable (every statement is CREATE OR REPLACE).
  After a model change: `python3 bq/generate_ddl.py emit-schemas`,
  commit, re-run the scripts (or `bq update --schema` additively). The
  exporter performs NO DDL at all: a missing table at export time
  fails loudly with the instruction to run the setup script, and
  transient insert failures are retried with backoff.

**Suggested event-router patch** (vendor `bq_export.py` and
`session_db.py` next to `review_design.py`; add near the other env
constants):

```python
INTEL_BQ_DATASET = os.environ.get(
    "AUTOCLOUD_INTEL_BQ_DATASET", "autocloud_rollout_intel")
import bq_export      # pylint: disable=g-import-not-at-top
import session_db     # pylint: disable=g-import-not-at-top
```

and in `handle_event`, after the streaming loop finished. Scope
preconditions: `target_template`, `status`, `data`, `insert_id`,
`session_id`, `get_bq_client`, `deidentify_content`, and
`deidentify_json_structure` must all be in scope (they are, just
before the existing agent_executions upload). The ENTIRE block —
including the guards — sits inside the try: nothing here may ever fail
the event.

```python
  # Export the finished rollout episode to the dedicated dataset.
  try:
    if target_template == "rollout-reviewer" and status == "SUCCESS":
      intel_bq = get_bq_client()
      if intel_bq:
        store = session_db.SessionStore(session_id)
        local_db = store.mount()  # read-only use: never persist() here
        is_deferred = (
            isinstance(data, dict) and data.get("type") == "deferred_check"
        )
        # IMPORTANT: the ref must be what the store bound the episode
        # to — insertId, falling back to the event's top-level "id"
        # (triggers.external_ref's exact fallback chain). Events with
        # neither got a SYNTHESIZED ref, which this router cannot
        # recompute — the find_finished fallback below covers them.
        ref = (
            data.get("unique_id") if is_deferred
            else (insert_id
                  or (data.get("id") if isinstance(data, dict) else None))
        ) or None
        episode_ids = (
            [bq_export.episode_id_for_ref(ref)]
            if ref
            else bq_export.find_finished_episodes(
                local_db, for_phase="ladder_complete")
        )
        for episode_id in episode_ids:
          try:
            summary = bq_export.export_episode(
                local_db,
                episode_id=episode_id,
                phase="ladder_complete",
                project=intel_bq.project,
                dataset=INTEL_BQ_DATASET,
                client=intel_bq,
                export_session=session_id,
                scrub_text=deidentify_content,
                scrub_json=deidentify_json_structure,
            )
            print(f"rollout-intel BQ export {episode_id}: {summary}")
          except bq_export.NotFinishedError as e:
            # Mid-ladder turn: nothing to export yet. Normal.
            print(f"rollout-intel BQ export skipped: {e}")
          except bq_export.UnknownEpisodeError as e:
            # Ref mismatch / wrong store: NOT normal. Export whatever
            # actually finished so nothing is silently lost.
            print(f"WARNING: rollout-intel BQ export ref mismatch: {e}")
            for fallback_id in bq_export.find_finished_episodes(
                local_db, for_phase="ladder_complete"):
              summary = bq_export.export_episode(
                  local_db, episode_id=fallback_id,
                  phase="ladder_complete", project=intel_bq.project,
                  dataset=INTEL_BQ_DATASET, client=intel_bq,
                  export_session=session_id,
                  scrub_text=deidentify_content,
                  scrub_json=deidentify_json_structure)
              print(f"rollout-intel BQ export {fallback_id}: {summary}")
  except Exception as e:  # pylint: disable=broad-exception-caught
    # Export problems must never fail the event. A RuntimeError here
    # means BigQuery rejected rows: safe to retry — consider
    # re-enqueueing via trigger_self_async() or alerting on this log
    # line rather than only printing.
    print(f"WARNING: rollout-intel BQ export failed: {e}")
```

**Phase 2 — after outcome labeling**: wherever your ground truth posts
the final label (outcome collector / labeling job), re-export with the
label included:

```python
bq_export.export_episode(db_path, episode_id=episode_id,
                         phase="outcome_final", client=intel_bq,
                         dataset=INTEL_BQ_DATASET,
                         scrub_text=deidentify_content,
                         scrub_json=deidentify_json_structure)
```

**One-time setup** — `setup-bq.sh` creates the dataset + tables and
then invokes `setup-views.sh` for the `*_latest` views (each script is
independently re-runnable; existing datasets/tables are never touched,
views are CREATE OR REPLACE):

```bash
PROJECT_ID=<project> ./compat/gcp-harness/bq/setup-bq.sh
# views alone (e.g. after adding a table):
#   PROJECT_ID=<project> ./compat/gcp-harness/bq/setup-views.sh
# equivalent, table by table:
#   bq mk --table --schema=bq/rollout_episodes.schema.json \
#     --time_partitioning_field exported_at --time_partitioning_type DAY \
#     ${PROJECT_ID}:autocloud_rollout_intel.rollout_episodes
#   ... and views: python3 bq/generate_ddl.py emit-views ${PROJECT_ID} | \
#     bq query --use_legacy_sql=false
```

## 6. What this changes about the clock contract

AGENT-CONTRACT.md's clock contract has two conformant shapes now:
(A) a harness scheduler opens checkpoints over REST and starts sessions
with header lines — the original export flow; (B) this document's
shape — the harness only delivers events, and `begin_review` +
`defer_verification` carry the ladder. Both end the same way: the
policy pack owns the schedule, the recorder owns the state, and the
outcome collector grades the episode afterwards.
