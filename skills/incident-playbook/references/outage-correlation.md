# Outage correlation - the "external" hypothesis, done honestly

Applies when: investigating the external/platform hypothesis from
rule 1, or when an incoming alert may duplicate a known platform event.

## Impact verdict discipline (exactly these three)

- IMPACTED - positive evidence ties this project's resources to a
  platform event.
- NOT_IMPACTED - claimable ONLY when the project provably has no
  resources of the affected product type in the affected location
  (verify with list_assets / list_services - absence of exposure is
  the one reliable negative signal).
- undetermined - no identified impact, but the project DOES have
  resources of the affected type in the affected location. Absence of
  identified impact is not absence of impact - platform-level detection
  lags. Say "no identified impact at this time"; never inflate it to
  NOT_IMPACTED.

## Correlation method

When a platform event is known or suspected, correlate on three axes:

- Time: the alert/symptom onset falls within a close window (~4 hours)
  of the event's start. Check the END time too - an event that finished
  before your symptoms began is a red herring, not a correlation.
- Product: the affected product matches the degraded component.
- Location: region/zone overlap with where your symptoms concentrate.

High correlation on all three -> note the duplication explicitly in the
incident report ("likely duplicate of platform event <id/desc>") so
responders don't double-investigate.

## Evidence on the current tool surface

No Service Health API is bound to this agent today. The platform-shaped
signal available to you is BREADTH:

- Multiple unrelated services degrading simultaneously in one region
  (query_metric across services; search_logs for infrastructure-class
  errors across workloads) is platform-shaped.
- One service degrading while its co-located neighbors stay healthy is
  workload-shaped - evidence AGAINST the external hypothesis.

When breadth is ambiguous and no platform event can be confirmed or
denied with bound tools, the external hypothesis stays OPEN as
undetermined - state that in the report. Never invent, assume, or
"recall" a platform incident the evidence does not show.

## Guard

The external hypothesis is the easiest place to park blame. It never
absorbs the incident by default - it must earn the verdict with the
same evidence bar as every other hypothesis, and it dies explicitly
when breadth says workload-shaped.
