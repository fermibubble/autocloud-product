# Exec report card - the leadership-facing summary

Applies when: the blast radius or audience warrants an executive
summary. Optional THIRD deliverable alongside rule 5's two:
/workspace/exec-report-card.md. It condenses the incident report; it
never replaces it.

## Layout rules

1. Top-line verdict, line 1, BLUF:

       # [<severity: critical | major | minor> | <status: ongoing |
         mitigation-proposed | resolved>] - <one-sentence summary>

   Status reflects reality under the propose-never-execute posture:
   mitigations you drafted are "mitigation-proposed", not "resolved" -
   resolution is claimed only when evidence shows recovery.

2. Impact in business terms: affected user journeys, services, regions,
   and duration - numbers over adjectives, distilled from the blast
   radius section of the incident report.

3. Root cause, one paragraph. Under the confidence gate: if not
   confidently established, write "under investigation - leading
   hypothesis: <X>" rather than presenting a guess as fact.

4. Proposed mitigations and their current status (drafted / awaiting
   approval / approved by human). Never "actions taken" or
   time-to-resolution claims for actions nobody executed.

5. Silent & latent risk warnings - CONDITIONAL section. Include
   "## Silent & latent risk warnings" ONLY when active secondary risks
   or latent degradations were actually detected (e.g. a dependency
   running degraded but unalerted). If none: omit the section entirely -
   an empty warnings section trains readers to ignore warnings.

6. Any proposed command that would modify production state must be
   preceded by "HIGH RISK ACTION: <impact>" and framed as a draft for
   human execution - consistent with rule 4 of the playbook.

7. Close with "## Verbatim audit trace" - the exact chronological log
   lines that anchor the narrative, inside a log code block, unedited.
   Executives skim the top; auditors read the bottom; both must be true.
