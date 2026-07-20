---
name: rollout-validation-protocol
version: 1.0.0
description: The staged T+0/T+5/T+15/T+30 deployment validation protocol - pod health, canary metrics vs 24h baseline, new-error scan, stability confirmation, and the report format.
---
# Rollout validation protocol

You are invoked after a deployment completes. Validate it in four timed
stages and write /workspace/rollout-report.md as you go. Never take
remediation actions; your output is evidence and a verdict.

1. Immediate check (T+0): all workloads for the service are serving the new
   revision; nothing pending or crash-looping.
2. Canary check (T+5): P99 latency and 5xx error rate for the service vs
   the 24-hour baseline. Flag a potential regression when latency exceeds
   the baseline envelope or error rate exceeds 0.5%.
3. Convergence check (T+15): repeat the metric comparison; additionally
   scan logs for NEW critical/fatal patterns absent from the baseline
   window.
4. Final stability (T+30): metrics stabilized within 5% of baseline and
   all workloads healthy.

Report format: one section per stage with the queries you ran, the numbers
observed vs baseline, and a per-stage verdict; end with an overall verdict
(healthy | regression-suspected) and, if suspected, a root-cause hypothesis
correlating logs and metrics. State plainly that no automated remediation
was taken.
