---
name: incident-playbook
version: 1.0.0
description: Parallel-hypothesis incident investigation - fan out competing hypotheses, assess blast radius, drive to a root cause, and produce the postmortem + comms structure.
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
