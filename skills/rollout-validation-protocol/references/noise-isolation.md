# Noise isolation - separating regression from external noise

Applies when: the evidence bundle or your extra queries contain errors.
Guard: this playbook can prevent an UNNECESSARY tighten and sharpen your
reasoning summary. It never loosens a policy fail (see SKILL.md).

## Investigate error types, not counts

Raw error counts mislead. Partition errors by what they are before
weighing how many there are.

## Regression signals (tighten toward regression-suspected)

Present in the target version's window but absent from the baseline
window:

- New stack traces or exception classes
- Internal database errors
- Unhandled exceptions
- Runtime crashes: out-of-memory kills, broken-pipe errors, thread
  starvation
- Recurring container restarts

The discriminator is NEW-IN-TARGET: if these appear under the target
version and not under the baseline, the rollout likely contains a
regression.

## External noise signals (do not tighten on these alone)

- Standard-library client-error logging: HTTP 4xx and 501 Unsupported
  Method are often written to error streams and surface as "errors"
  without being server-side regressions.
- Scanner-probe traffic: publicly exposed endpoints are constantly
  probed by vulnerability scanners. Scanner traffic often SPIKES during
  rollouts because IP or load-balancer reassignment exposes new
  endpoints to scanners - a 4xx/5xx/501 burst correlated with the
  rollout can be discovery noise, not regression.
- The baseline-consistency test: if traffic-shaped errors are consistent
  with baseline patterns, or represent standard handling of invalid
  external input, they are not evidence of a rollout regression.

## Quantify the split when you can

Use `search_logs` to partition the error window: by status class (4xx vs
5xx), and by path shape (probe paths like /admin, /.env, /wp-login vs
the service's real routes). Compare each partition against the same
partition in the baseline window with separate queries. State the
partition result in your reasoning summary - "5xx on real routes
doubled; the 4xx burst is probe paths also present at baseline" is a
verdict-grade sentence.
