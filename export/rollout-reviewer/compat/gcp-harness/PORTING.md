# Porting guide — AutoCloud GCP harness (GCE VM / Cloud Run)

Exact steps to add the trustworthy rollout reviewer to your deployed
harness (the sandbox + agent containers from your deployment guide).
Verified facts this guide relies on: both containers run with
`--network=host` (localhost is shared), the sandbox executes agent
commands via `sandbox_server.py`'s `POST /run`, deferral runs on Cloud
Tasks (`autocloud-verification-queue`), and the scorer grades every
execution from prompt-template rubrics into BigQuery.

## Step 1 — Add the export to your build

From your exported build directory (`~/autocloud_export`):

```bash
# 1a. Copy this export folder into the build context
cp -R /path/to/export/rollout-reviewer ~/autocloud_export/rollout-reviewer

# 1b. Install the skill into your first-party skills registry
#     (it lands in the image at /skills/ -> /workspace/cloud/agents/autocloud/skills/)
cp -R ~/autocloud_export/rollout-reviewer/skill/trustworthy-rollout-review \
      ~/autocloud_export/cloud/agents/autocloud/skills/

# 1c. Append the addon to the SANDBOX Dockerfile (plain docker build —
#     no buildx contexts needed since the export is now in-context)
cat >> ~/autocloud_export/Dockerfile << 'EOF'

# ---- Trustworthy Rollout Reviewer addon ----
COPY rollout-reviewer/ /opt/rollout-reviewer/
RUN uv python install 3.12 \
    && cd /opt/rollout-reviewer/servers/rollout-intel && uv sync --frozen \
    && cd /opt/rollout-reviewer/servers/gcp-observe && uv sync --frozen \
    && chmod +x /opt/rollout-reviewer/scripts/*.sh /opt/rollout-reviewer/compat/gcp-harness/rr \
    && cp /opt/rollout-reviewer/compat/docker/entrypoint-addon.sh /usr/local/bin/entrypoint-addon.sh \
    && chmod +x /usr/local/bin/entrypoint-addon.sh
EXPOSE 7610 7611 7600 7601 7620 7621
CMD ["/usr/local/bin/entrypoint-addon.sh"]
# ---- end addon ----
EOF
```

The addon CMD wraps your `entrypoint_sandbox.sh` (Chrome + mcp-proxy
start unchanged) after bringing up the reviewer stack. Episode store
defaults to `/workspace/rollout-reviewer-run/episode-store.db` — on the
VM that is your `~/artifacts` volume, so episodes survive container
restarts.

## Step 2 — Build and push (your existing commands, unchanged)

```bash
cd ~/autocloud_export
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/autocloud-repo/sandbox:latest -f Dockerfile .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/autocloud-repo/sandbox:latest
# then hot-reload per your guide's Scenario A (pull + restart on the VM)
```

Live-GCP evidence: the sandbox runs as `autocloud-runner@…` with viewer
roles — set `LIVE_GCP=1` and `GCP_PROJECT` in the container env to
point gcp-observe at real projects instead of the sim (the VM's service
account credentials apply; `roles/viewer` + `logging.viewer` +
`monitoring.viewer` you already grant are sufficient). Leave unset to
keep the sim for testing.

## Step 3 — Wire the agent (no ADK/Jetski tool development)

Because the sandbox executes commands via `POST /run`, the agent drives
the entire reviewer surface through its EXISTING run_command tool and
the `rr` CLI:

```json
{"cmd_list": ["/opt/rollout-reviewer/compat/gcp-harness/rr", "checks", "<episode>", "T+5"],
 "workdir": "/workspace", "timeout": 120}
```

1. Load the skill from
   `/workspace/cloud/agents/autocloud/skills/trustworthy-rollout-review/SKILL.md`.
2. Append `HARNESS-ADDENDUM.md`'s block to the agent's system
   instructions — it maps each skill tool name to its `rr` command
   (works identically under ADK and Jetski; the `sandbox_` prefix is
   handled by Jetski's own instructions).
3. Session input: the AGENT-CONTRACT §2 header. Your Event Router
   already formulates the prompt — extend it to include the
   `EPISODE:/STAGE:/SERVICE:/PRIOR:` lines (episode id comes from
   Step 4).
4. Optional but recommended — seal free-hand command output too: a
   3-line patch to your sandbox server makes every `POST /run` result
   carry a signed observation envelope, so `gcloud`/`kubectl` output
   gets the same tamper-evident provenance as the typed tools. See
   `HARNESS-MINTING.md` (patch, key handling, evidence tiers) and prove
   it with `python3 compat/gcp-harness/test-sandbox-minting.py`.

## Step 4 — The clock, on your Cloud Tasks deferral

Your `defer_verification` (Cloud Tasks → Event Router → agent) IS the
checkpoint clock. Two wiring points:

- **Episode creation (once per deploy event):** simplest is no Event
  Router parsing at all — hand the raw audit-log entry to the session
  and let its first action be `rr begin '<event JSON>'`: parsing
  (platform-authoritative fields only), episode creation (deterministic
  id from `insertId`, so redelivery dedupes), and opening the due
  checkpoint happen server-side in one call. Driver-side alternative:
  `POST /intel/triggers` with the raw event, or the older explicit
  `rr new-episode --service <name> …` / `compat/clouddeploy-to-episode.py`.
- **Per checkpoint:** the deferred task's payload
  (`{"type": "deferred_check", "unique_id": <the trigger's insertId>}`)
  goes to the session verbatim; `rr begin` resumes the right episode and
  stage (or answers `ladder_complete`/`closed` for a late timer). After
  the session records, the `rr record` response's `next_check` block is
  what the agent arms `defer_verification(next_check.unique_id,
  next_check.delay_seconds)` with — recorder-returned values, as its
  LAST action, exactly once (see `SESSION-LIFECYCLE.md` §3 and the
  skill's clock spec). It already reflects the policy's ladder, any agent
  proposal (`--next-check-minutes`/`--next-check-reason`; tightening
  honored, loosening clamped to policy bounds), and the exit criteria.
  A null `next_check_at` means the ladder is closed — schedule
  outcomes, not another session. If your session store lives in GCS
  between checks, mount/persist it with `session_db.SessionStore`
  (`SESSION-LIFECYCLE.md` §4).
- **Outcomes:** at your chosen horizons (a deferred task works), post
  ground truth: `rr outcome <episode> --horizon 24h --final-label
  healthy|regressed|rolled_back --source collector` — from YOUR
  monitoring, never from the agent's verdicts.

## Step 5 — Scoring integration

- Copy `rubrics/*.txt` into your rubrics directory
  (`experimental/autocloud/scorer/rubrics/`): nine per-principle binary
  rubrics plus a weighted composite, all in your template format
  (feature-relevance gate, `verdict_score`, classifier outputs, your
  placeholders) - the hourly Vertex batch scorer picks them up
  unmodified, and each execution aggregates per principle in BigQuery
  (see `rubrics/README.md`).
- Optional deterministic pre-score: run
  `rr validate <episode> --require-quoted-evidence` in the scorer job
  (or from the agent post-record) — exit code 0 is a mechanical
  schema/cross-ref pass the LLM rubric then builds on. Its exit codes
  (2/3/4/5/6) classify failures for your BigQuery dashboards.

## Step 6 — Verify on the VM

```bash
# inside the VM, through the sandbox container:
docker exec sandbox /opt/rollout-reviewer/scripts/smoke-test.sh   # 7 checks
# or through the sandbox /run endpoint (the path the agent uses):
curl -s -X POST http://127.0.0.1:5001/run -H 'Content-Type: application/json' \
  -d '{"cmd_list": ["/opt/rollout-reviewer/compat/gcp-harness/rr", "episode", "<id>"], "workdir": "/workspace"}'
```

Seven PASSes from the smoke test inside your image = port complete;
then one real event through the sink → Event Router → agent →
`rr record` → scorer is the full production loop.
