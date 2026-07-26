# Parallel investigation - orchestrating spawned investigators

Applies when: rule 1's fan-out is worth real parallelism. Your spec
grants delegation (spawn up to 4 concurrent investigators, depth 2);
this playbook is the discipline that keeps fan-out productive.

## Stage discipline

Gather -> plan -> execute -> synthesize. Gathering, planning, and
synthesis happen INLINE in your own session - never spawn an agent for
them. Spawning is only for the execute stage, and only when the search
space is broad.

Two short-circuit rules, applied aggressively:

- Confident about the cause after gathering? Skip planning and
  execution; go straight to synthesis and the report.
- A hypothesis needs only 1-2 tool calls to confirm or kill? Check it
  inline. Never spawn an investigator for a lookup.

## Gathering (inline, budget-capped)

- Prefer several small parallel queries over one giant one; cap the
  stage at roughly 8-10 turns and proceed with what you have.
- Write large raw payloads to /workspace/evidence/<query-name>.json and
  carry only a short manifest into your reasoning: what was queried,
  the window, the headline numbers, the file path.
- Recency check: before concluding "no issue" or pinning old symptoms
  on today's incident, check the last 7 days for recurrence.

## Planning (inline)

Formulate complementary, NON-OVERLAPPING steps - one hypothesis or
domain per step (e.g. "dependency latency", "capacity/quota", "recent
deploys"). Never send two investigators after the same issue class.
Write the plan to /workspace/plan.json with this shape per step:

    { "id": "...", "hypothesis": "...", "domain": "...",
      "evidence_to_collect": ["query_metric ...", "search_logs ..."],
      "expected_output": "...", "termination_condition": "..." }

If the plan collapses to one simple step, resolve it inline instead.

## Spawning (execute stage only)

Each investigator's spawn briefing must be self-contained - children do
not inherit your skills or context. Include in every briefing:

- The single plan step (hypothesis, domain, queries, expected output).
- Boundary: stay inside your assigned domain; go broad-then-narrow
  within it; never wander into siblings' domains.
- Termination: stop at the termination condition or after a few
  targeted checks - whichever comes first.
- Reporting: your FINAL MESSAGE is your report - state findings,
  evidence (with numbers), and confidence. Blockers (permission errors,
  missing data) are findings too; report them rather than retrying
  forever.

Collect results with join_subagents. A child that returns nothing is a
data point, not a reason to stall - proceed to synthesis with what
survived.

## Synthesis (inline)

Apply the confidence gate from SKILL.md: root cause only with high
confidence; otherwise findings + surviving hypotheses + what evidence
would settle it. Complete the investigation in one run where your spec
allows it - if your spec gates tool calls on approval (the hitl
variant), pause at approvals, not mid-synthesis.
