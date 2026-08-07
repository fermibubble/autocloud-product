# Rollout Reviewer — Customer User Journeys

A **CUJ** is one thing a customer is trying to get done, told from
their side in plain words, with the measure that says it worked. This
set was **mined independently** — 29 candidates from three lenses:
documented release-engineering practice, the governance journeys
autonomous agents create, and per-persona jobs-to-be-done — then
**adversarially critiqued** for groundedness and craft, and finally
**consolidated into three high-level journeys**. Each journey contains
the specific moments the mining surfaced; the moments are the map, the
three journeys are the territory.

**The operating rule:** every roadmap item names the CUJ — and the
moment inside it — that it improves. A feature that improves no
journey improves nothing.

| # | CUJ | Who lives it | Success is measured by |
|---|---|---|---|
| 1 | Ship changes safely without watching them | Developers, feature owners | Regressions stopped at small exposure; everything self-serve |
| 2 | When production breaks, find the change and recover in minutes | On-call, incident responders | Minutes to culprit; detection-to-recovery under 15 minutes |
| 3 | Have a reviewer we can trust — and prove everything it did | Every engineer; platform leads, compliance | Verdicts any engineer can verify from the evidence; zero incidents from unearned authority |

---

## CUJ-1 — Ship changes safely without watching them

I ship many times a day — binaries, flag ramps, config pushes — and I
should not have to babysit any of it. If a change is unhealthy I want
it stopped while few users are affected; if it is held I want the
evidence so I can fix it or overrule it, self-serve, without paging
anyone. And the safety should be the same whether the change rode a
deploy pipeline or a flag flip, because an outage does not care which
one it was.

*Who: every developer and feature owner. Frequency: many times a day —
the everyday loop. Success: regressing changes stopped before reaching
a small fraction of the fleet; routine status and hold-handling fully
self-serve; flag and config changes under the same review as binaries.*

**The moments inside this journey:**

- *Ship without babysitting it* — merge, move on, get a clear verdict per stage.
- *Follow my change and act on a hold* — self-serve status; evidence I can act on; fast hold-to-fix.
- *Ramp a flag or config change as safely as a deploy* — staged evidence for the changes that hit 100% instantly today.
- *Proceed despite a failing verdict, on the record* — overrule in seconds when I know something the reviewer does not; my name and reason attached.

## CUJ-2 — When production breaks, find the change and recover in minutes

I got paged. My first question is "what changed?" and my second is
"how do I make it stop?" I need the culprit named with evidence in
minutes — across deploys, flags, and config, most of which I did not
make — and then a safe path back: a rollback with its hazards flagged
and recovery confirmed, or an emergency fix through a compressed path
that is fast but never dark.

*Who: on-call engineers and incident responders. Frequency: per page —
weekly per rotation; the highest-stakes journey. Success: median time
to an evidence-backed culprit (or confident exoneration) in minutes,
with false exonerations near zero; detection-to-confirmed-recovery
under 15 minutes; zero dark deploys — every emergency change still
gets evidence and review.*

**The moments inside this journey:**

- *Pinpoint the change behind the regression* — one answer across every change source, solid enough to act on.
- *Roll back and confirm recovery* — spread checked, hazards (one-way migrations) flagged, metrics verified after; the human executes, the reviewer prepares and verifies.
- *Ship an emergency fix under pressure* — break-glass that is fast but never off the record.

## CUJ-3 — Have a reviewer the organization can trust — and prove everything it did

We will not hand production judgment to a machine on faith. The
reviewer earns our trust the same way a new engineer would: it has to
show good judgment before we give it any real power, it takes on more
responsibility as its track record grows, and if it makes a bad call,
we pull that responsibility back. The verdicts themselves have to hold
up too — when it flags a regression, any engineer should be able to
open the rollout, look at the evidence it points to, and follow how it
reached that conclusion. It should be right because its reasoning is
sound, not because it got lucky. And whenever someone wants to know
why it decided something — an engineer today, a postmortem team next
week, an auditor next year — the full story is right there: what it
saw, which rule applied, and who approved what.

*Who: every engineer who opens a rollout — plus platform leads,
service owners, compliance, and leadership for the governance moments.
Frequency: the verdict-trust moments run with every rollout; the
governance moments are episodic — per adoption wave, per audit, per
incident — and decide whether the other two journeys are allowed to
exist.*

**Success metrics** — one per promise the narrative makes:

| The promise | Metric | Target |
|---|---|---|
| Shows good judgment before it gets power | Verdict-vs-outcome precision and recall over labeled episodes, measured *before* any authority is granted | Gate floor met before any gate opens (e.g. precision ≥0.80 over ≥50 labeled episodes for Gate A) |
| Responsibility grows with the track record | Authority expansions backed by a met numeric floor and a named approver | 100% — no demo-driven or deadline-driven grants |
| Bad calls pull responsibility back | Time from a tripped revocation trigger to demotion; incidents attributable to authority its record did not support | Demotion is automatic, in minutes, no meeting; attributable incidents: zero |
| Any engineer can follow the reasoning | Median time for an engineer to read a regression call and confirm it from the cited evidence | Under 5 minutes, measured on sampled verdicts |
| Evidence a human can check | Material claims in a verdict that link to reproducible evidence | 100% — a claim with no checkable evidence fails review |
| No leap of logic | Sampled verdicts with a complete reasoning chain — every conclusion traceable to cited observations, no unsupported step | ≥95% on human-scored samples; every flaw found becomes a filed fix |
| Right for sound reasons, not luck | Correct verdicts graded "supported by the evidence it cited" vs. "correct but lucky" in outcome review; honest abstention when evidence was thin | Lucky-correct rate trending to zero; abstention scored as success, never coerced to a guess |
| The full story, available to anyone | Time to produce any decision's evidence, rule, and approver — months later | Under 10 minutes, straight from the record — same answer for an engineer, a postmortem, or an audit |

**The moments inside this journey:**

- *Follow any verdict's reasoning as a human* — the evidence chain and the logic laid out so a regression call convinces in minutes, on its merits, not because the machine said so.
- *See its judgment proven before it gets any power* — a track record against real outcomes, not a demo.
- *Approve it as part of the change process* — with the same rigor as any control the org relies on.
- *Decide what it may do, and where* — written down, owned, and reviewed.
- *Give it more authority only as its record earns it* — one step at a time.
- *Take authority back after a bad call* — in minutes, with a clear path to earn it back.
- *Bring a new service under review in a day* — and see the first verdicts match the owner's own judgment.
- *Understand any wrong verdict* — see exactly what it saw and where its reasoning broke, so the same miss cannot repeat.
- *Know when it did not know* — missing data produces an honest "no call," never a quiet guess.
- *Show the full story of any decision* — evidence, rule, approver — to any engineer today, a postmortem, or an audit, in minutes.

---

## How This Set Was Critiqued

Two adversarial reviews shaped this set before consolidation — a
groundedness critique ("is this genuinely common, or product-flavored
wishful thinking?") and a craft critique ("is this a user's journey,
or a pitch?"). What they changed:

- **Names lost their solution language** — the feature is not the job.
- **The agent left the subject position.** Narratives that read "the agent compares… surfaces… verifies" were rewritten from the user's side; a journey where the product is the protagonist is a pitch.
- **Success measures moved from paperwork to outcomes.** "100% of overrides justified" grades bookkeeping; "overrides later judged correct stay high" grades reality.
- **Three missing moments were added:** emergency fixes under pressure (where gate bypasses actually happen), flag/config-only changes (most user-facing risk at mature orgs), and the everyday status check.
- **Trust journeys were re-scoped, not deleted.** The critics rejected them as everyday customer journeys with invented frequencies; they survive inside CUJ-3 as what they are — episodic, platform-and-leadership moments in one trust lifecycle.

**Deliberately excluded, and why:** multi-service release-train
coordination (org-model-specific; its core judgment is CUJ-1) and
velocity/awareness dashboards (valuable exhaust of the episode record,
not a journey the product must own). If operating evidence promotes
either, it joins through the same critique.

---

*Companion to the
[Rollout Reviewer standard](rollout-reviewer.md). The standard's nine
principles are the control structure that makes these journeys
trustworthy; the [At a Glance](rollout-reviewer.md#at-a-glance) table
maps principles to the CUJs they power.*
