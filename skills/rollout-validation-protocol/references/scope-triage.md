# Scope triage - attribute evidence before weighing it

Applies when: any evidence is about to influence your verdict.

Classify every evidence source into exactly one of:

- TARGET - the service/revision this episode reviews. Its signals decide
  the verdict.
- DEPENDENCY - upstream or downstream of the target. Its signals explain
  target symptoms (a dependency's errors can cause the target's latency)
  but are not themselves the target's regression.
- UNRELATED - co-located in the same project without a dependency link.
  Its signals are excluded from the verdict; say that you excluded them.

Rules:

- Never attribute a co-located neighbor's errors to this rollout. Use
  `list_services` / `list_assets` to establish what else lives in the
  project before weighing project-wide signals against the target.
- Sibling stages of the same release (multi-target or multi-region
  promotions) are CONTEXT: note their state in your reasoning when
  visible, but their signals are not this checkpoint's evidence.
- Concurrent unrelated rollouts are pruned like any unrelated resource -
  their deploy events and their errors belong to their own episodes.
- Identity from the context pack governs scope. If identity is an
  inferred CANDIDATE, every scope conclusion inherits that uncertainty -
  state it, and lean toward insufficient-evidence when attribution
  itself is in doubt.
