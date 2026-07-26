# Stuck savings - why a reported recommendation is not being realized

Applies when: a resource you (or a prior sweep) flagged as idle or
oversized is still there - the recommendation exists but the savings
never land. On GKE-backed fleets the usual reason is that the cluster
autoscaler WANTS to scale down and cannot. Diagnose why and attach the
blocker to the finding; a recommendation without its blocker just gets
re-reported forever.

## The blocker taxonomy

The autoscaler logs its no-scale-down decisions with explicit reason
ids. The eight that matter:

- Node auto-provisioning resource limits exceeded
- Node group already at configured minimum size
- kube-system pods that cannot be moved off the node
- Pod Disruption Budgets too tight to permit eviction
- No spare capacity elsewhere to reschedule the node's pods
- Pods annotated safe-to-evict: false
- Non-replicated pods (nothing to reschedule to)
- Nodes annotated scale-down-disabled

## Evidence queries

The autoscaler's decisions live in the cluster-autoscaler-visibility
log. Query with search_logs using Cloud Logging filter syntax:

    log_id("container.googleapis.com/cluster-autoscaler-visibility")
    resource.type="k8s_cluster"
    resource.labels.cluster_name="<cluster>"
    jsonPayload.noDecisionStatus.noScaleDown.nodes.reason.messageId:"no.scale.down."

Narrow by messageId to identify the specific blocker, e.g.:
"no.scale.down.node.pod.kube.system.unmovable",
"no.scale.down.node.node.group.min.size.reached",
"no.scale.down.node.minimal.resource.limits.exceeded".

Skip this playbook entirely when the fleet has no GKE assets
(list_assets shows none) - the taxonomy is autoscaler-specific.

## Reporting the blocker

Extend the stuck finding with: the blocker (from the taxonomy), the
evidence (matched log reason ids), and a draft unblocking proposal
where one exists (e.g. a PDB adjustment, removing a scale-down-disabled
annotation) - framed like every other remediation: a proposal with its
risk stated, executed by nobody. Where the blocker is a deliberate
choice (a min-size floor an operator set), say so and mark the savings
as intentionally forgone pending a human decision.
