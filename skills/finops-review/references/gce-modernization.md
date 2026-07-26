# GCE modernization - generation and storage upgrade advisory

Applies when: the sweep surfaces older-generation compute (N1/N2 class)
or legacy Persistent Disk. Everything here is ADVISORY - findings and
draft Terraform for human review, per rule 4. Nothing is provisioned,
snapshotted, or migrated by you.

## Discovery on this surface

- Inventory candidate instances with list_assets; utilization history
  with query_metric; native rightsizing advice with get_recommendations.
  Recommender output is the anchor - metric analysis refines it, never
  replaces it.

## Rightsizing discipline

- Size from sustained percentiles (P95-style over the longest window
  the metrics support), not from peaks or provisioned capacity.
- Never map cores 1:1 across generations - newer generations deliver
  more performance per core; a 1:1 mapping silently overprovisions and
  erases the savings the upgrade was for.

## Storage mapping (the part that breaks people)

- Newer generations do not support legacy Persistent Disk - the finding
  must pair the machine-type change with a Hyperdisk migration, never
  propose one without the other.
- Hyperdisk performance (IOPS/throughput) is provisioned INDEPENDENTLY
  of disk size. Derive provisioned values from historical peak usage,
  not from the old disk's size-implied limits - assuming size parity
  either wastes money or bottlenecks the workload.
- Multiple disks in one project: note Hyperdisk Storage Pools as a
  consolidation option in the draft.

## Honest inputs (state as assumptions in the report)

Three inputs are NOT verifiable on the current tool surface - carry
them as named assumptions with the finding, never as facts:

- Committed Use Discount position (existing CUDs can penalize early
  migration; Flex CUDs may not) - no billing tools are bound.
- Target-generation capacity in the specific region/zone (stockouts are
  real) - no availability API is bound.
- Utilization beyond the queryable window, if the workload's history
  exceeds it.

## Finding shape

Per rule 3, plus for modernization findings: current shape -> proposed
shape (machine type AND disk type/provisioned-performance), before/after
monthly cost with the assumptions named, migration risk (data move,
downtime window, rollback path), and the draft Terraform for the target
state. Recommend staged adoption - non-production first - as part of
the proposal; the staging decision, like everything else, is the
human's.
