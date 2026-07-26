---
name: incident-playbook
version: 1.1.0
description: Parallel-hypothesis incident investigation - fan out competing hypotheses, assess blast radius, drive to a root cause, and produce the postmortem + comms structure - with on-demand playbooks for parallel investigation orchestration, platform-outage correlation, and executive reporting.
---
# Incident playbook

1. Frame 2-4 competing hypotheses immediately (e.g. deploy regression,
   dependency failure, capacity, external). Investigate them in parallel -
   spawn sub-investigations where available rather than serializing.
2. Blast radius first: which services, regions, and user journeys are
   affected, and since when. Numbers over adjectives.
3. Evidence per hypothesis: metrics and log patterns that confirm or kill
   it. Kill hypotheses explicitly; a surviving hypothesis is your root
   cause candidate.
4. Mitigation is proposed, never executed, unless the goal explicitly
   grants it - and then only through approved tool calls.
5. Deliverables: /workspace/incident-report.md (timeline, blast radius,
   root cause, evidence) and /workspace/comms.md (stakeholder notification
   drafts: impacted teams, status, next update time).

## The confidence gate

State a root cause ONLY with high confidence and sufficient evidence.
Without it, say so plainly: recap what was investigated, present every
finding and surviving hypothesis, and name exactly what evidence would
settle it. A guessed root cause is worse than an honest open question -
it sends responders the wrong way.

## Investigation playbooks (read on demand)

Detailed playbooks ship in this package at
/skills/incident-playbook/references/. Read the ones that apply; skip
the rest:

- Spawning parallel investigators (rule 1) ->
  references/parallel-investigation.md (stage discipline, non-overlapping
  domain plans, spawn briefings, synthesis).
- The "external" hypothesis, or an alert that may duplicate a known
  platform event -> references/outage-correlation.md (impact verdict
  discipline, correlation windows, dedup).
- Leadership-facing summary warranted (major blast radius or exec
  audience) -> references/exec-report-card.md (optional third
  deliverable: /workspace/exec-report-card.md).
