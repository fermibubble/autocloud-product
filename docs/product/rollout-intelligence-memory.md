# Rollout Intelligence — Memory Design

**How the reviewer remembers: the memory flywheel, explained end to end — and why this memory can advise without ever being able to lie.**

Memory is where agent systems quietly go wrong. They remember their own
opinions as facts, retrieve by vibes, and let stale knowledge outlive
the world it described. This document explains how Rollout Intelligence
avoids all three — first as concepts anyone can follow, then (in a
separate section) as the implementation that enforces them. The
one-sentence summary: **memory may only ever advise — reality writes
the labels, humans promote the lessons, and every read is scoped,
graded, and audited.**

Companions: [rollout-reviewer.md](rollout-reviewer.md) (the
trustworthy-autonomy standard) and
[rollout-reviewer-system-design.md](rollout-reviewer-system-design.md)
(where memory sits in the whole system).

---

## The flywheel

Everything in this design is one loop:

```
   ① review (sealed evidence) ──▶ ② episode recorded ──▶ ③ reality labels it
        ▲                                                        │
        │                                                        ▼
   ⑤ memory returns as ◀── ④ humans promote ◀── candidate lessons emerge
     sharper context          durable facts       (≥3 labeled supporters)
     (precedents, priors,     (dossiers)
      tuned scrutiny)
```

Each turn of the loop is gated by a **different authority**: the
recorder decides what was concluded, reality decides what was true,
humans decide what becomes durable, and hard trust rules decide what
memory is allowed to do about any of it. That separation is the entire
trick. A system that lets the same party write, grade, and consume its
own memory will eventually believe itself; this one cannot.

The running example throughout: the `checkout` service has just
deployed revision `v184`, and the reviewer is working its checkpoints.

---

## ① The review becomes an episode

Every rollout the reviewer touches becomes an **episode**: a permanent,
append-only record of one rollout of one service. Into it goes
everything the review produced — each checkpoint's verdict and report,
every sealed evidence envelope the verdict cited, every decision the
recorder took (including the ones that *rejected* the agent: a
softening verdict that was refused is stored too, because refusals are
part of the history), and every scheduling decision with the agent's
proposal beside what the schedule actually did.

Two design choices matter here, and both are about honesty later:

**Records, not summaries.** The episode keeps the evidence itself —
signed, scoped, freshness-stamped — not a paraphrase of it. Six months
from now, anyone can re-open the episode and check the reasoning
against the same bytes the reviewer saw. Memory built on summaries
inherits every bias of the summarizer; memory built on records can be
re-litigated.

**One writer, one door.** Only the recorder writes episodes, and it
writes them once — checkpoints complete exactly one time, and a re-run
session finds the completed record instead of overwriting it. There is
no side channel by which an agent (or anyone) can quietly amend
history. What the store says happened is what happened.

At this point the episode is a *diary*, not yet a *lesson*. The
reviewer's `regression-suspected` at T+30 is an opinion on file. The
flywheel's next station decides whether it was a good one.

---

## ② Reality grades the episode

Here is the trap this design exists to avoid: an agent that learns from
its own verdicts becomes more confident, not more correct. If
yesterday's "healthy" call is today's training signal, every mistake
compounds into doctrine.

So the episode store keeps two forever-separate columns: what the
agent **concluded** (`final_verdict`) and what actually **happened**
(`final_label`). The label is written by an outcome collector reading
monitoring at fixed horizons after the rollout — did latency really
hold, did the revision get rolled back — or by a human. It is *never*
written by the agent, and nothing the agent records can influence it.

For checkout v184 — the same rollout the standard's Principle 1 walks
through — the reviewer said `regression-suspected` at T+30;
at the 24-hour horizon the collector observes the rollback and labels
the episode `rolled_back`. Now — only now — the episode is *learnable*.
And the verdict-versus-label comparison across many episodes yields the
two numbers the whole system is judged by:

- **falseSafe** — said healthy, was regressed. The dangerous error.
- **falseHalt** — cried wolf. The trust-eroding error.

The reviewer is thereby a measured instrument with a published error
rate, graded by an authority it cannot argue with.

One subtlety: the episode's label is first-writer-wins and never
rewritten (per-horizon outcome observations are idempotently upserted,
but the label itself sticks). A human who disagrees with a collector's label
doesn't edit history — they file a correction through the feedback
channel, which is itself recorded. History accumulates; it never
mutates.

---

## ③ Lessons emerge — but only with support

A labeled corpus makes patterns visible. Checkout stabilizes within ten
minutes, five rollouts in a row. Scanner traffic spikes during IP
reassignment, again. The reviewer notices these and may write them down
— but *writing down* and *becoming truth* are deliberately far apart.

What the agent files is a **proposal**: a candidate durable fact,
explicitly tagged with how it is known — a hypothesis from observation,
an assertion from evidence — and citing the episodes behind it. The
learning layer then does bookkeeping no one has to trust an LLM for: a
proposal is surfaced for human review only when it has support from at
least **three distinct labeled episodes** — episodes reality graded,
that existed before the proposal did — and proposals contradicted by
labeled evidence are blocked outright. Popularity among the agent's own
unlabeled opinions counts for exactly nothing.

Surfacing is still not truth. It is a queue for station ④.

---

## ④ Humans promote what becomes durable

Long-term memory lives in per-service **dossiers**: small sets of typed
facts — "p99 baseline is 180ms," "stabilization window is 10 minutes,"
"traffic is diurnal with a Monday peak" — that future reviews consult.
Because these facts can influence real machinery (a stabilization
window can shorten a review ladder), the bar for entry is the highest
in the system:

**Every claim knows how it is known.** Each dossier entry carries an
epistemic type — *hypothesized, asserted, inferred, observed, approved*
— and the agent can only ever file the weak end of that scale.
Promotion to operational status is a human act, stamped with who
verified it — and to make a claim *govern*, the promoter must also
upgrade it to `approved`; activation without that upgrade leaves it
advisory. Anything operationally consequential reads **only**
human-approved or directly-observed claims; a hypothesis, however
popular, can never move machinery.

**Every claim can die.** Dossier facts are bitemporal — valid from,
valid until, activated when, deactivated when — so the system can
replay "what did we believe last Tuesday?" and get a time-correct
answer. Facts expire on schedule, and more importantly, **reality
invalidates them**: when checkout re-platforms from architecture v1 to
v2, every architecture-sensitive claim (baselines, windows, traffic
profiles, resource envelopes) is expired automatically, with the reason
journaled, *before* the first v2 episode consults anything. The
reviewer's memory of checkout becomes suddenly, correctly, humbler. A
v1 baseline masquerading as v2 truth is the memory equivalent of stale
evidence — and it is structurally impossible here.

The lifecycle of one fact, end to end:

```
"stabilization_window_minutes: 10"
  proposed (hypothesized, citing ep_a, ep_b, ep_c)
    — surfaced as a suggestion (3 labeled supporters; still `proposed` in the journal)
      → active (promoted by an SRE, upgraded to approved; verifier stamped)
        → expired (architecture v1→v2; reason journaled)
```

---

## ⑤ Memory returns as sharper context

The loop closes where the next review begins. Before the agent looks at
a single live metric, its context pack already carries: this episode's
prior checkpoints, the service's dossier (with each claim's epistemic
type in plain view), and **precedents** — past rollouts of this shape,
*with their labels*.

Precedent retrieval is the easiest thing in this design to get wrong,
so it is deliberately boring — SQL discipline, not semantic vibes:

- **Hard filters first.** Labeled episodes only. Architecture-
  compatible only — an episode from the old architecture is history,
  not precedent. Time-correct under replay: a query "as of" last month
  cannot see labels that arrived since.
- **Scope widens on a ladder, never into soup.** Same service first; if
  that is too thin, same service family; then same runtime. Each rung
  is tried only when the previous one came up short, and the rung used
  is recorded in the result.
- **Balance is enforced mechanically.** The top matches from *each*
  side — healthy and unhealthy — by fingerprint similarity. If one side
  is short, the result says so (`insufficient_precedent: true`) rather
  than backfilling with more of the other. A one-sided precedent set is
  how confirmation bias gets institutionalized; this system reports its
  ignorance instead.
- **Every agent-facing read is journaled.** Which tool asked, with what
  filters, what came back, as of when. The agent's memory reads are as
  auditable as its verdicts.

And then the single rule that makes all of this safe to hand to an
agent: **memory advises; evidence decides.** Precedents and dossier
facts shape *where the reviewer looks* — run the error-partition query
it might have skipped, distrust the metric known to lag — and precedent
influence is tighten-only: history can buy a rollout more scrutiny,
never less. No memory of any tier can satisfy a policy rule, soften a
verdict, or stand in for a live observation. The one carefully governed
exception: a human-approved dossier value (a stabilization window) may
shorten the review ladder — and even then only past the coverage floor,
after every policy rule has had a stage to run. That exception is
exactly why the dossier's promotion bar is the highest in the system. When checkout v184's
precedents whisper "slow-burn error creep," the verdict still rests
entirely on this session's sealed envelopes. The whisper just made sure
the right query got run.

That is one full turn. The review that benefits from memory produces
the next episode, reality grades it, and the wheel keeps its momentum —
which is the difference between a system that *accumulates* and one
that *learns*: this one can tell you, for every remembered fact, who
vouched for it, since when, and what would make it forgotten.

---

## The memory tiers

The flywheel's stations map onto four tiers of storage:

| Tier | What it holds | Lifetime | Writer | Status |
|---|---|---|---|---|
| **Session context** | The context pack assembled for one checkpoint: identity, policy, prior verdicts, retrieved memory | One session | Server-side, per session | Shipping |
| **Episodic memory** | Episodes: checkpoints, sealed observations, decisions, reports (stations ①–②) | Forever, append-only | The recorder | Shipping |
| **Long-term memory** | The labeled corpus (precedents) and dossiers (stations ③–④) | Until reality invalidates | Collector + humans | Shipping, per-deployment |
| **Institutional memory** | Org docs, runbooks, postmortems (NotebookLM); live topology (One Graph) | External | External systems | Planned integration |

---

## Local-first now, fleet-wide next

The memory hot path is deliberately **local and offline**: the episode
store lives beside the reviewer (an embedded database; any SQL engine
by configuration), reachable over loopback only. A review can gather,
reason, and record with zero external calls — a network partition can
degrade the reviewer's *context*, never its ability to record truth.

This works because memory's consistency needs are asymmetric. *Within*
an episode, consistency must be strong — the tighten-only floor only
works if T+15 sees T+5's verdict in the same store. *Across* episodes,
memory is advisory by rule — and advisory data tolerates staleness by
design. Strong-local, eventual-global is not a compromise; it is the
correct shape.

Fleet scale is therefore post-processing: episodes ship asynchronously
to a central corpus (the store is an append-only journal, so uploads
are idempotent and replay-safe), and outcome labels land centrally.
v184 makes the point concretely: its checkpoints recorded locally in a
sandbox with no egress, and by the time the 24-hour label arrived, that
sandbox was gone — the label has to land somewhere durable. Central
memory is served back through the **same tool contracts** the reviewer
already uses, so nothing about the skill changes when memory goes
fleet-wide; and if the memory service is slow, stale, or down, the
review proceeds with honestly-reduced context ("no usable precedent" is
a first-class answer, not an error).

---

## Implementation

Everything above is enforced in `servers/rollout-intel` (identical in
the portable export). This section maps concept to code.

### Data model (`models.py`, `db.py`)

| Table | Role in the flywheel |
|---|---|
| `episodes` | Station ①/②. `final_verdict` and `final_label` are separate columns; learning joins `final_label IS NOT NULL` |
| `checkpoints` | One per stage, UNIQUE(episode, stage), completes exactly once; carries report, policy result, `next_check_at` |
| `observations` | Sealed envelopes as stored (scope, freshness, signature-verified flag) |
| `decisions` | Verdict decisions, rejected softening attempts, `next_check` schedule audit |
| `outcomes` | Ground-truth labels per horizon; source constrained to `collector \| webhook \| human` |
| `feedback` | Human corrections (`human_override`, …) — the append-only alternative to editing history |
| `dossier_journal` | Station ④: bitemporal claims with `epistemic_type` and status lifecycle |
| `retrieval_audit` | Station ⑤: every memory read journaled |

Storage: SQLite by default (WAL, session-per-operation transactions),
any SQLAlchemy URL by configuration. Append-only discipline is stated
policy enforced by the write paths (episodes advance status; nothing
UPDATEs history).

### Enforcement map

| Concept | Enforced by | Enforcement |
|---|---|---|
| Memory never satisfies policy | `policy.py` `evaluate()` consumes only verified envelopes — memory is structurally absent | Structural |
| Agent never learns from its own verdicts | `learning.py` + `retrieval.py` join labeled episodes only | Structural, unit-tested |
| Labels from reality only | Outcome endpoint (the production face) validates `source` and `final_label`; episode label first-wins; corrections via `feedback`. (The fixtures loader is a test-only side door) | Structural |
| Proposal ≠ truth | `dossier.py`: agent restricted to `hypothesized`/`asserted`; `activate()` is the human door, stamps `owner_verified_by` | Structural, unit-tested |
| Support threshold | `learning.py` `MIN_SUPPORT = 3` distinct labeled episodes; contradiction blocking | Structural |
| Only vetted claims move machinery | `dossier.py` `governed_value()` honors `approved`/`observed` active claims only; governed windows also floor-guarded so no rule loses its stage (`service.py`) | Structural, unit-tested |
| Decay & invalidation | Bitemporal `as_of` reads (UTC-normalized via `db.to_utc_z`); `sweep_expired`; `invalidate_architecture` (dossier.py, triggered from `Intel.create_episode`) over `ARCH_SENSITIVE_FIELDS` = {p99_baseline_ms, error_rate_baseline, stabilization_window_minutes, traffic_profile, resource_envelope} | Structural, unit-tested |
| Scoped, balanced retrieval | `retrieval.py`: rungs service → family → runtime (monotonic, recorded); top-2 healthy + top-2 unhealthy by fingerprint Jaccard; `insufficient_precedent` honesty; `labeled_at <= as_of`; architecture hard filter on every rung | Structural, unit-tested |
| Reads audited | `db.audit_retrieval` on the agent-facing reads (context pack, similar-episodes, dossier tool); provenance is per-tool. Operator REST dossier reads are the un-audited replay face | Structural |
| Tighten-only memory influence | Skill spec (`outcomes.md`) + per-principle scoring rubric | Prose + scored |

### Surfaces

The reviewer touches memory through three tools — `get_context_pack`
(assembles tiers 1–3 for the session), `find_similar_episodes`,
`get_dossier` / `propose_dossier_update` — over MCP or the `rr` CLI
bridge. Humans touch it through REST: outcome posting, feedback,
dossier promote/reject, decision-quality metrics, and the learning
suggestions queue.

### Deployment notes

- The Ensemble memstore projection of active dossier claims
  (`MemoryProjector`) is enabled only when `ENSEMBLE_TOKEN` is set;
  without it the journal is the sole store. With it, projection is
  best-effort and repairable (`dossier sync`) — the journal remains the
  truth either way.
- The export seeds its precedent corpus from evaluation fixtures via a
  test-only endpoint; a real corpus accrues from real labeled episodes.
- Unit coverage for this layer lives in the export's test suite
  (dossier state machine and bitemporal reads, retrieval widening and
  filters, learning's labeled-only joins, outcome label-once).

---

## What this design does not claim

- **Fleet scale is designed, not built.** Today each deployment's
  memory is its own; the central corpus, async uploader, and shared
  memory service are roadmap.
- **Institutional memory is planned.** NotebookLM and One Graph appear
  in the tier table as integrations-to-be; nothing consumes them yet.
- **The corpus starts empty.** Precedent quality is a function of
  labeled volume; the moat accrues with production time and cannot be
  bootstrapped.
- **Suggestion ≠ truth, and promotion ≠ infallibility.** Humans should
  expect to reject some well-supported suggestions — and the bitemporal
  journal exists precisely so a promoted mistake can be retired with
  its history intact.
