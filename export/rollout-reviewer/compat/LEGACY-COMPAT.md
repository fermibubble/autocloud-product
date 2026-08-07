# Legacy compatibility — running trustworthy review on a harness built for the legacy skill

Your harness already runs (or nearly runs) the legacy `rollout-review`
skill. This document maps every tool and behavior that skill uses onto
this export, so the trustworthy reviewer slots into the same harness
with minimal rewiring — keeping what your system already has, and adding
trust guarantees where the legacy layer had prose.

The through-line: **keep your tools, move the authority.** Your query
tools, your chat tool, your scheduler all stay. What changes is where
truth lives (the episode store, not state.json), what counts as
evidence (signed envelopes, not raw output), and what a verdict must
carry (the epistemic record, not a status word).

## Tool-by-tool mapping

| Legacy tool / behavior | Keep it? | In this export | Trustworthiness added |
|---|---|---|---|
| **Log & metric query tools** (Step 4: query log/metric sources per window) | Yes — for investigation | `query_metric` / `search_logs` on gcp-observe (`LIVE_GCP=1` hits your real GCP project through the same code path) | Every result becomes a **signed envelope** — only envelopes satisfy policy. Your existing raw tools may still inform narrative, but a number without an envelope cannot decide a verdict. Validate bridged tool outputs against `schemas/evidence-envelope.schema.json` |
| **`gcloud deploy releases describe` / `rollouts list`** (Step 1.5: pipeline discovery) | Yes — moved out of the review session | `compat/clouddeploy-to-episode.py`: converts Cloud Deploy release/rollout JSON into `POST /intel/episodes` — your existing gcloud discovery becomes the episode-creation feed | Discovery output becomes an owned, fingerprinted episode instead of per-session re-discovery; the review session starts from `get_context_pack`, not from re-running gcloud |
| **`send_google_chat_message`** (Step 7: Initiated / Issue / Success milestones) | Yes — keep your tool | `compat/notify-from-record.py` renders the legacy's three message formats **from the recorded episode** — pipe its stdout to your chat tool | Notifications become projections of recorded truth: sent AFTER `record_checkpoint`, carrying verdict + confidence + evidence, never free prose that can drift from the record. The "Issue" message includes the causal chain and the record's confidence basis |
| **`defer_verification`** (lifecycle: schedule re-check, stop tools, end turn) | Yes — it becomes the clock | Your defer/scheduler mechanism drives the checkpoint ladder (AGENT-CONTRACT §4): fire one review session per checkpoint at T+0/+5/+15/+30 | Target state: defer moves OUT of the reviewer session into your orchestration. Transitional state (least rewiring): the reviewer may call defer only AFTER `record_checkpoint`, as its last action — the recorder has the truth either way, and a dead session is re-fired harmlessly (replay-safe recording) |
| **`state.json`** (Step 0: `/workspace/rollouts/<id>/state.json`, verifications_done/pending) | Transitional only | The episode store owns all cross-session state; `get_context_pack` returns prior verdicts, identity, policy — everything state.json approximated | State gains an owner, versioning, and an audit trail. state.json may persist as session-local scratch, but nothing read from it may satisfy a check — it was the legacy skill's biggest fragility (mutable, unversioned, keyed on a log insertId) |
| **Report file** (google3 path + final response) | Yes — path remapped | `/workspace/rollout-report.md` (+ the same content recorded durably via `record_checkpoint.report_md`) | The report is a projection of the record; it now embeds the machine-validatable epistemic record. Copy it to your legacy path too if downstream tooling expects it |
| **`kubectl` / `terraform` remediation commands** (Step 8: copy-pasteable CLI) | Yes — inside the draft | The record's `proposed_action` (`schemas/proposed-action.schema.json`): goal, blast radius, approvers — CLI text lives inside the draft as never-execute steps for the human | `posture: draft-only` is schema-enforced; an executed action is unrepresentable. The legacy's "do not ask permission" posture inverts: autonomy belongs to your harness config, not skill prose |
| **Status vocabulary** (`SUCCESS \| FAILURE \| DEGRADED \| ONGOING`, + SOAKING/PENDING/PAUSED) | Mapped | `healthy \| regression-suspected \| insufficient-evidence` — SUCCESS→healthy; FAILURE/DEGRADED→regression-suspected; ONGOING/SOAKING/PENDING/undecidable→insufficient-evidence | The recorder enforces the vocabulary and rejects softening (`policy_conflict`). "I don't know yet" becomes expressible — the legacy could only round it to a confident word |
| **10-minute post-convergence monitoring** (Step 6) | Yes — generalized | The T+15/T+30 checkpoints carry the stability analysis (skill spec `outcomes.md`: leak shapes, restart recurrence, slow-burn creep) | Durability claims get a clock: `valid_through` / `reassess_if` on the verdict; outcomes later graded independently at 30m/2h/24h via `POST /intel/episodes/{id}/outcome` |
| **Trigger events** (audit log / Pub/Sub / deferred_check) | Yes | Same events feed your clock layer; trigger TEXT reaching the session is untrusted data (skill spec `trust-boundary.md`) | The legacy's own "Audit Log Discrepancy" caution becomes structural: controller status is orchestration fact, never health fact, and pressure text gets quarantined as `quoted_evidence` |

## What your harness must add (the trustworthiness delta)

Three genuinely new pieces, all shipped here:

1. **The two servers** (`servers/`) — the signed-evidence channel and the
   recorder with its tighten-only floor. Everything above routes through
   them.
2. **The epistemic record** — your agent's reports now embed it;
   `scripts/validate-epistemic-record.py --episode <id>` checks every
   session's output mechanically.
3. **Outcome labels** — something in your system (your monitoring, your
   incident process, or `sim/outcome_collector.py` against the sim)
   posts ground truth so the reviewer is eventually graded
   (`schemas/outcome.schema.json`).

## Suggested migration order

0. On the AutoCloud GCP deployment (GCE VM / Cloud Run)? Start at
   `gcp-harness/PORTING.md` — it composes everything below into six
   copy-paste steps for that exact stack (rr CLI over your sandbox
   /run endpoint, Cloud Tasks as the clock, scorer rubric drop-in).
   Generic containerized harness? `docker/DOCKER-INTEGRATION.md` covers your
   sandbox image specifically: the skill drops in via your existing
   `third_party_skills_ctx` build context, and the servers bake in with
   `docker/Dockerfile.addon` + an entrypoint wrapper (your Chrome +
   mcp-proxy startup unchanged). Your agent then adds the two MCP
   endpoints — they speak the same streamable-http your mcp-proxy
   already uses.
1. Stand up the servers (`run-stack.sh`), keep your harness running the
   legacy skill — wire `clouddeploy-to-episode.py` into your deploy
   events so episodes accumulate silently. Nothing user-visible changes.
2. Swap the skill: load `skill/trustworthy-rollout-review/` with the
   AGENT-CONTRACT instructions; bridge the five core tools
   (TOOL-CONTRACT §minimum viable). Keep `send_google_chat_message`
   wired through `notify-from-record.py`; keep your defer as the clock.
3. Turn on validation in your eval loop (`--episode`, exit codes), then
   outcome posting. From here the falseSafe/falseHalt metrics
   (`GET /intel/metrics/decision-quality`) start meaning something.
