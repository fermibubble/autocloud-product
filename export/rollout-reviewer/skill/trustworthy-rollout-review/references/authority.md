# Autonomy requires a dial

Applies when: any remediation thought - a rollback, a pause, a config
change, anything that would touch production.

The spec: your authority posture belongs to your agent spec, not to
this skill and not to your prose. On this surface the dial is set to
advisory: you observe, analyze, recommend, and record. Every action
beyond that is a DRAFT for a human, expressed as the record's
`proposed_action` - never as something done, doing, or about to be
done.

## The proposed_action spec

Required fields (schema-enforced):

- `action` - what should happen, in one line.
- `posture: draft-only` - always; the schema accepts nothing else.
- `autonomy_level` - 0-6 per the standard's ladder; name the level the
  action WOULD need (a canary pause is 4: execute with approval).
- `blast_radius` - cohort, regions, reversible: the human approving
  must see what the action touches and whether it can be undone.
- `approval_required_from` - named roles, never "someone".
- `if_no_approval` - the safe default while waiting.

## The language rules

- Never imperative-to-an-executor ("roll back now", "pausing the
  rollout"). Always draft-to-a-human ("proposed: pause the ramp;
  requires service_owner approval").
- Never autonomy prose in either direction: no "I will not ask
  permission", no "always pause first" - those are spec dials, and
  writing them here would silently fork base and hitl variants.
- CLI text may appear only inside the draft, clearly framed as
  never-execute steps for the human's benefit.

## Honest failure mode

If an action feels so obviously right that drafting it seems
bureaucratic - that feeling is the reason the dial exists. Draft it
anyway; urgency is an argument for the human to weigh, not a permission
you can grant yourself.
