# Hazard classes - what the oracle probes

Applies when: reading a hazard report or fast-forward result; deciding
whether a change manifest plausibly carries a slow-burn risk.

Hazards are compiled from the deploy event's change manifest, not from
telemetry: a dependency bump, config change, flag, or code touch maps to
feature traits, and traits map to hazard classes. A hazard is a
QUESTION about the future ("does this candidate leak?"), not a finding;
the disposition and outcome answer it. `hazard_id` values (`hz_` + hex)
are stable per manifest - cite them verbatim.

## The six classes

- `resource_lifecycle` - resources acquired per unit of work but not
  released: connections, file handles, sockets, memory. Fails at a
  ceiling, not gradually; the ladder window sees only the shallow slope.
- `rate_balance` - production and consumption rates that no longer
  balance: retry amplification, queue growth, batch backlog. When the
  amplification factor exceeds 1, depth compounds under steady load.
- `clock_expiry` - anything with a TTL: credentials, tokens, leases,
  certificates, caches. Correct until the first expiry or rotation,
  which lands after the ladder by construction.
- `state_boundary` - behavior changes when accumulated state crosses a
  boundary: schema growth, counter overflow, pagination cliffs,
  cache-fill transitions.
- `concurrency` - interleavings that only occur under sustained load or
  rare timing: lock ordering, double-release, read-modify-write races.
- `agent_longevity` - long-running worker/agent processes that degrade
  with age: drifting internal state, unbounded histories, scheduled-work
  interactions.

## The three MVP playbooks, in reviewer terms

These are the shapes the oracle currently probes end-to-end; recognize
them in results and explain them in reports.

### Connection/handle leak (resource_lifecycle)

Trigger shape: a pool/db/http dependency bump (e.g. `pg-pool` major
version). Mechanism: the candidate acquires a connection per work cycle
and misses the release path; open handles rise linearly with cycles and
never plateau. Ladder telemetry stays in-band because the slope times
thirty minutes is small; the handle ceiling is crossed hours later.
Report language: state the per-cycle growth, the ceiling, and the
first-divergence age in cycles; the production impact is exhaustion -
refused work, error burst, restart churn - at a projectable time.

### Retry amplification (rate_balance)

Trigger shape: a retry/timeout config change (e.g. `retry_max` 1 -> 4).
Mechanism: with dependency failure probability p and up to k attempts,
expected extra load m can exceed 1; each failure wave seeds a larger
one and queue depth compounds under flat traffic. Ladder windows show
healthy request metrics while retries and queue depth climb. Report
language: name the amplification factor, the queue-growth shape, and
the first-divergence age in requests; the production impact is latency
collapse and saturation well after promotion.

### Credential expiry / reuse-after-rotate (clock_expiry)

Trigger shape: an auth-client dependency bump. Mechanism: the candidate
caches a credential and keeps using it after rotation or TTL expiry
(`reuse_after_rotate`); everything works until the first rotation,
which the ladder never reaches (TTL typically >= 3600s). Report
language: state the TTL, the first-divergence age in `cred_age_s` or
rotations, and whether stale reuse produced side-effect attempts; the
production impact is an authentication outage or, worse, silent stale
side effects at first rotation.

## Discipline

- A hazard with no counterexample is not a finding: report the
  disposition the oracle actually reached, nothing stronger.
- Hazards outside the probed classes (or listed unsupported) are open
  unknowns - name them in the record's unknowns, never absorb them.
- Hazard features come from the change manifest; quote manifest items
  (name, from, to) when explaining mechanism - that is the causal root.
