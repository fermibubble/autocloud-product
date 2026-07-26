# Skill Contribution Guide (Ensemble)

How to author, package, and publish a skill for this product. This
replaces the earlier agentskills.io-era guide — Ensemble shares its
spirit (progressive disclosure, small entrypoints) but differs in
contract details that will break your publish if you follow the old
rules. Differences from the old world are called out inline.

## 1. Package shape

One directory per skill under `skills/`, with `SKILL.md` at its root:

```
skills/<skill-name>/
├── SKILL.md            # the contract body — loaded into context on skill load
└── references/         # on-demand playbooks — materialized, read via file_read
    └── <playbook>.md
```

- The bundle glob (`skills/*` in `ensemble.bundle.yaml`) treats EVERY
  direct child of `skills/` as a skill. Never drop a stray file or an
  empty directory there — `ensemble apply` fails the ENTIRE bundle on
  the first entry without a valid `SKILL.md` (specs, rubrics, and
  datasets after it don't sync either). The old platform "silently
  skipped" invalid skills; Ensemble hard-fails, on purpose.
- Everything in the package is materialized read-only into the agent
  sandbox at `/skills/<skill-name>/…` on every load. Ship only what the
  agent should read: no generation debris, no test prompts, no
  READMEs-for-humans, no raw data dumps.
- Limits (generous; you will not hit them with prose): 10 MiB package,
  200 files, 512 KiB body.

## 2. Frontmatter

```yaml
---
name: my-skill            # REQUIRED. DNS label, must equal the directory name
version: 1.0.0            # REQUIRED. Strict semver — the CLI refuses to publish without it
description: >-           # REQUIRED. 10–1024 chars — this is the retrieval surface
  What the skill does and the symptoms/tasks that should trigger it,
  keyword-dense.
labels: { domain: ops }   # optional; skill_search can filter on labels
---
```

- `version` is the old world's biggest gap: agentskills.io needed only
  name+description; Ensemble's CLI lint requires strict semver. A
  missing version kills the whole apply.
- **Versions are immutable.** `name@version` publishes exactly once;
  editing content without bumping the version makes `ensemble apply`
  print `unchanged` and silently never republish. Every content change
  bumps the version, and the agent-spec refs move with it.
- Unknown frontmatter keys (`allowed-tools`, `requires`, anything
  custom) are **silently dropped** at publish — they neither error nor
  enforce anything. Tool permissions live in agent specs, not skills.

## 3. The house style: contract body + on-demand playbooks

Keep `SKILL.md` a tight contract (target ≤ ~100 lines): the invariant
rules, the deliverable paths, the verdict/report vocabulary — the
things that are true in every session. Put situational depth in
`references/*.md` playbooks, each opening with a one-line "Applies
when:", and give the body a when-to-read index:

```markdown
## Playbooks (read on demand)
- Errors present in the evidence -> references/noise-isolation.md
- STAGE is T+15 or T+30 -> references/stability-checks.md
```

- Relative links WITHIN a package always resolve (they materialize
  together). Links ACROSS skills (`../other-skill/…`) resolve only if
  both skills happen to be loaded in the same sandbox — the registry
  has no dependency edges. Never do it; if another skill's content is
  required, say "load <skill-name>" by registry name or inline what you
  need.
- See `skills/rollout-validation-protocol/` for the reference example
  of the pattern.

## 4. Write against the real tool surface

Skills instruct agents that have NO shell, NO cloud CLIs, and no
network egress (`python:3.12-slim`, `network: deny`). Never instruct
`gcloud`/`kubectl`/`bq` execution — those instructions are physically
unexecutable and train the model to hallucinate. The bound surfaces:

- `gcp-observe` (MCP): `query_metric`, `search_logs`, `list_services`,
  `list_assets`, `get_recommendations`. `search_logs` accepts raw Cloud
  Logging filter syntax — log-filter knowledge ports directly.
- `rollout-intel` (MCP, rollout agents): `get_context_pack`,
  `run_stage_checks`, `evaluate_policy`, `record_checkpoint`,
  `find_similar_episodes`, `get_dossier`, `propose_dossier_update`.
- Builtins per spec: `file_read`/`file_write` (plus `glob`/`grep` where
  granted).

CLI text may appear ONLY inside drafted remediation proposals, clearly
framed as never-execute drafts for a human — consistent with the
product's read-only-first posture. A skill that instructs mutation does
not ship.

## 5. Respect the product contracts

- **Verdicts**: use the consuming agent's enforced vocabulary (e.g.
  `healthy | regression-suspected | insufficient-evidence` for rollout;
  the recorder rejects anything else). Always leave an epistemic escape
  hatch — "insufficient evidence" must be expressible; never force a
  binary call.
- **Deliverable paths**: rubrics score `file_written` checks against
  exact paths (`rollout-report.md`, `incident-report.md`,
  `finops-report.md`, `design-review.md`). Changing a path breaks the
  agent's evals.
- **Autonomy is a spec dial, not skill prose**: never write "do not ask
  the user for permission" or "always/never pause" into a skill — the
  same skill serves base and `-hitl` spec variants.

## 6. Retrieval

`skill_search` ranks lexically over name + description + the first
~4 KB of the body, and returns a short top-k list showing only
name/version/description. Write descriptions symptom-keyword-dense
("OOMKilled", "IP_SPACE_EXHAUSTED"), not generic prose; content buried
in `references/` is invisible to search, so anything retrieval-relevant
belongs in the description or early body.

## 7. Publish and verify

```sh
# from the product root, with an autocloud-product tenant token
export ENSEMBLE_TOKEN=...          # scripts/bootstrap.sh mints one
go run -C ../ensemble/cli . apply . --dry-run   # expect: would publish <name>@<ver>
go run -C ../ensemble/cli . apply .             # publish
go run -C ../ensemble/cli . apply .             # re-run: everything `unchanged`
```

The token matters: an unauthenticated apply publishes into the default
tenant and the product's agents will not see your skill.

Checklist before publishing:
- [ ] `version` present, semver, bumped if content changed
- [ ] dir name == frontmatter `name`
- [ ] no `gcloud`/`kubectl`/foreign-platform tool references outside
      never-execute remediation drafts
- [ ] every `references/*.md` named in the body exists in the package
- [ ] deliverable paths match the consuming agent's rubric
- [ ] agent spec `skills.refs` updated to the new version (ALL spec
      variants together — scripted/hitl twins must keep their
      one-section delta)
- [ ] eval: the consuming agent's suite still passes
      (`scripts/run-suite.sh <agent>`); new behavior worth measuring
      gets a rubric criterion or dataset case
