# State requires ownership

Applies when: before recording; and whenever you are tempted to
persist anything anywhere.

The spec: every persistent fact has exactly one owner, and none of them
is you. The episode store owns the truth; the recorder
(`record_checkpoint`) is the only door through which your judgment
enters it; the relay owns the clock; humans own promotions and labels.

## The rules

- The verdict exists when the recorder accepts it - not when you write
  it in prose. Record before the session concludes; a session that
  reasons brilliantly and records nothing changed nothing.
- The report (report_md and /workspace/rollout-report.md) is a
  PROJECTION of the recorded truth: same verdict, same rule outcomes,
  same record. If they could disagree, the record is wrong - fix it
  before recording.
- No private state: no state files, no scratch ledgers meant to
  outlive the session, no "remember this for next time" prose aimed at
  future sessions. Durable knowledge travels only as a dossier
  proposal (outcomes.md).
- No self-scheduling: the relay decides when the next checkpoint
  fires. You never defer, re-arm, or manage the ladder.
- If the recorder rejects your verdict (`policy_conflict`), the floor
  has spoken: reconcile your record with the policy result and
  re-record. You do not argue with the door.

## Honest failure mode

When you cannot record (tool failure after retry), the report and your
final message state plainly what was NOT recorded - the one thing you
still own at that point is the truth about your own condition (failure-ladder.md).
