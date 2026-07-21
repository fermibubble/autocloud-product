---
name: dossier-maintenance
description: How to read service operational dossiers and propose updates without ever writing memory directly. For rollout reviewers consulting per-service baselines, stabilization windows, and traffic profiles.
version: 1.0.0
---

# Dossier maintenance

A service's *operational dossier* is its governed profile: baselines,
stabilization windows, traffic patterns, ownership notes. It lives in the
rollout-intel journal; what you see in memory or `get_dossier` is a
read-only projection of revisions a human activated.

## Reading

- `get_context_pack` already includes the dossier claims for the episode's
  service — read them there first.
- `get_dossier(service, as_of?)` for another service or a historical view.
- The memory store `memstore://project/rollout-dossiers` mounts at
  `/memory`; topics are `dossier:<name>.<env>.<region>:<field>`. When
  searching it, always scope with `topic_prefix` set to
  `dossier:<name>.<env>.<region>:` — never rely on ranked search to keep
  services apart.

## Trust rules (non-negotiable)

- Every claim carries an `epistemic_type`. Treat them differently:
  - `approved` / `observed` — governed truth; may inform interpretation
    and scheduling emphasis.
  - `asserted` / `inferred` — plausible context; weigh, don't lean.
  - `hypothesized` — an open question, not knowledge.
- A dossier claim NEVER satisfies a policy rule and NEVER substitutes for
  live evidence. Policy + live signed evidence decide; the dossier only
  shapes how you interpret and what you look at next.
- If a claim contradicts live evidence, trust the live evidence and say so
  in your report.

## Writing (you can't — you propose)

You have no write access to the dossier store; that is deliberate: the
system never learns from its own verdicts. When you observe something
durable about a service (a consistent baseline, a stabilization pattern),
call `propose_dossier_update` with:

- `epistemic_type`: `hypothesized` (a pattern you suspect) or `asserted`
  (something a tool result stated) — the only types you may use.
- `rationale`: cite the observation ids or episodes that support it.

The proposal lands as `proposed` and is invisible to every dossier read
until a human promotes it. Never re-propose the same fact in the same
session; once recorded, it is in the review queue.
