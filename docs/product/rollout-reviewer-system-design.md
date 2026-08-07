# Rollout Reviewer — System Design

**An autonomous reviewer for every production rollout — one the organization can trust, that gets smarter with every deploy, and that moves failure detection from "after users noticed" toward "before it ships."**

---

## 1. Abstract

Every deploy is a bet placed on production. Today, most of those bets
are watched by nobody: a fixed bake timer, a dashboard glance, an
on-call engineer's divided attention. Rollout Reviewer is an autonomous
agent that reviews **every** rollout at policy-defined checkpoints and
renders verdicts a human can verify without redoing the work.

It stands on two pillars. **Trustworthy Autonomy**: every verdict is
backed by tamper-evident evidence and a complete, machine-checked
reasoning trail — and the agent can neither touch production nor weaken
a hard SLO rule. **Rollout Intelligence**: every reviewed rollout is
graded against what actually happened, so the reviewer's accuracy is a
measured number that improves with every deploy — and what one rollout
teaches, the next one knows.

The trust loop — sealed evidence, recorded verdicts, rejected softening
attempts, outcome grading — runs end-to-end today, demonstrated on two
independent agent runtimes, alongside an implemented preventative core
(Rollout Fast-Forward). Fleet-scale memory and the topology and
knowledge integrations are the roadmap.

---

## 2. The Two Pillars, Expanded

### Trustworthy Autonomy — trust as architecture, not aspiration

The first pillar rests on one insight: **you do not make an agent
trustworthy by asking it to be careful.** Prompted diligence fails
silently, exactly when it matters. Instead, every behavior that would
make a verdict untrustworthy is made either impossible or indelibly
visible — the trust lives in the architecture around the agent, where
it can be inspected, not in the model's disposition, where it cannot.

Unpacking the abstract's claims one at a time:

- **"Tamper-evident evidence."** Every observation is cryptographically
  sealed at its source, bound to its service, time window, and
  freshness. The agent becomes a *courier* of evidence rather than a
  witness to it: it can carry, select, and reason about measurements,
  but it cannot fabricate one, alter a digit, borrow a number from the
  wrong service, or pass off stale data as current — any of those
  breaks the seal, and the verdict-recording layer checks seals rather
  than trusting couriers.
- **"A complete, machine-checked reasoning trail."** A verdict never
  travels as a bare label. It carries the observations it rests on
  (each citing sealed evidence), the alternative explanations it
  considered, its confidence *and the honest basis for it*, what
  remains unknown, and — most demandingly — the concrete checks that
  would overturn it. A validator enforces this structure mechanically,
  so "the reasoning is complete" is a lint result, not a compliment.
  This is what makes a verdict cheap to trust: a human verifies in
  minutes what they would otherwise re-derive in an hour.
- **"Cannot weaken a hard SLO rule."** Beneath the agent sits a
  deterministic policy floor that evaluates the same sealed evidence
  without a model in the loop. The recorder re-runs it on every
  recording and rejects any verdict softer than what the rules found —
  and stores the rejected attempt for audit. The agent's judgment may
  *tighten* the machine's answer (suspicion the rules missed), never
  loosen it. "Insufficient evidence" is a first-class verdict, so
  uncertainty is never rounded up to reassurance.
- **"Cannot touch production."** The reviewer's tool surface is
  read-only, and remediation exists only as a structured draft naming
  its blast radius and required approvers — in the record's schema, an
  *executed* action is not even representable. How much autonomy the
  system exercises is configuration owned by the organization (§7),
  never initiative taken by the agent.

One further guarantee stitches these together: anything the agent reads
from production — log lines, error messages, tool payloads — is data,
never instructions. A log line that tries to instruct the reviewer is
quoted verbatim, flagged, and surfaced in the report: an attack on the
reviewer becomes evidence in its findings. The net effect of the pillar
is a shifted burden of proof — the organization stops asking "do we
believe the agent?" and starts asking "do the seals, the records, and
the floor check out?", which is a question machines answer.

### Rollout Intelligence — graded by reality, compounding by design

The second pillar mirrors the first: **left ungraded, an agent grows
more confident, never more correct — and confidence is not a
credential.** Every deploy is a bet; here, every verdict is one too —
placed on the record, settled by what production actually does, and
scored in numbers the whole organization can read. Grading makes the
reviewer measurable; keeping what the grading teaches makes it better
with every deploy.

- **"Graded against what actually happened."** Every reviewed rollout
  becomes a permanent episode, and at fixed horizons afterward an
  outcome collector — reading monitoring, not the agent's opinions —
  labels it with the ground truth: healthy, regressed, or rolled back.
  The agent's conclusion and reality's label are stored as separate,
  never-merged facts. Their comparison across the fleet yields the two
  numbers that define the reviewer: **falseSafe** (said healthy, was
  regressed — the dangerous error) and **falseHalt** (cried wolf — the
  trust-eroding one). The reviewer is a measured instrument with a
  published error rate, judged by an authority it cannot argue with.
- **"Improves with every deploy."** The labeled corpus is not a
  scoreboard; it is training signal for the *system* (not the model's
  weights — its knowledge). Recurring patterns surface as candidate
  lessons only when supported by multiple independently labeled
  episodes; humans promote the ones that deserve to become durable,
  per-service facts; and stale knowledge is invalidated by reality
  itself — a re-architected service automatically sheds every claim
  that described its old incarnation.
- **"What one rollout teaches, the next one knows."** At the start of
  every review, the agent already holds the service's history: labeled
  precedents of similar rollouts *with their outcomes*, and the
  human-vetted dossier of the service's quirks. Memory is
  deliberately advisory — it directs where to investigate, and
  precedent influence can only buy a rollout *more* scrutiny, never
  less; the verdict still stands exclusively on this session's sealed
  evidence. (The full memory
  design, from episode to promoted lesson, is
  [rollout-intelligence-memory.md](rollout-intelligence-memory.md).)

### Why it takes both

Each pillar alone is a familiar failure. Intelligence without trust is
the confident dashboard-watcher nobody dares put in front of a gate —
accuracy you cannot audit is accuracy you cannot use. Trust without
intelligence is a beautifully auditable system that repeats last
quarter's mistakes forever. Together they form the loop the rest of
this document elaborates: trust earns the reviewer its place on real
rollouts; running on real rollouts builds the labeled corpus; the
corpus sharpens accuracy; and measured accuracy — not sentiment — is
what moves the autonomy dial (§7).

---

## 3. Problem Statement

Three deficits keep rollout safety where it is:

**The trust deficit.** Autonomous review is easy to prototype and
almost impossible to trust. An LLM that watches dashboards and says
"looks good" is confidently wrong in exactly the cases that matter, and
when it is right, nobody can tell *why* — so no organization puts it in
front of a production gate. The blocker for autonomy is not model
quality; it is that **an unverifiable verdict is worthless at any
accuracy**, because every verdict must be re-checked by the human it
was supposed to relieve.

**The memory deficit.** The organization's rollout knowledge lives in
heads and postmortems. The service that always spikes scanner traffic
during IP reassignment, the dependency that makes Tuesday deploys
risky, the metric that lags five minutes behind reality — each team
relearns these the hard way. Nothing structural carries what rollout N
taught into rollout N+1.

**The timing deficit.** Detection is reactive. By the time a regression
is visible, users have felt it; by the time the postmortem lands, the
context is gone. *[Fill with internal data: N of last quarter's Sev-2+
incidents were rollout-caused, median detection X hours — each one a
candidate for this system.]* The industry answer — canary analysis —
narrows the window but still only tells you what already went wrong.

The opportunity: rollout reviews are a bounded, repetitive,
evidence-rich task — precisely where an agent should excel — **if** its
trustworthiness is engineered as rigorously as its intelligence.

---

## 4. Critical User Journeys

### CUJ: Have a reviewer the organization can trust — and prove everything it did.

> "We will not hand autonomy to an agent based on faith. The reviewer
> earns our trust the same way a new engineer would: it has to show good
> judgment. When it flags a regression, any engineer should be able to
> open the rollout, look at the evidence it points to, and follow how it
> reached that conclusion. It should be right because its reasoning is
> sound, not because it got lucky."

### CUJ: Every rollout makes the next one safer.

> "We keep paying for the same lessons twice. The error spike that hits
> every release because the config lands before the binary that reads
> it; the connection-pool leak that never shows on the first deploy of
> the day but topples the third; the retry storm that turns a slow
> dependency into a full outage at peak traffic — each of these has a
> known root cause, but known to two or three engineers, until they
> leave. When a rollout is reviewed, everything this organization
> has learned about that service should already be at the table: how
> similar rollouts actually turned out, what its known quirks are, and
> how the reviewer's own past calls were graded. And when the reviewer
> thinks it has learned something new, it should have to prove it to us
> before we rely on it."

### CUJ: Catch it before users do — and eventually, before it ships.

> "Today we find out about a bad rollout when users do. What we want is
> to find out minutes into the canary — with the reason, not just an
> alarm. But the failures that hurt us most no canary window can catch:
> the connection leak that needs six hours, the retry storm that needs
> Monday's peak, the certificate that expires on the weekend. For those,
> we want the rollout's future rehearsed before real traffic touches it
> — simulate the deploy, fast-forward its clock through tomorrow, and
> show us the trajectory that breaks as evidence we can replay, not as a
> guess. And if a change looks like the ones that burned us before, it
> should get more scrutiny and a slower ramp without anyone having to
> ask. A page telling us something broke is the floor; a rehearsal
> telling us what would break, before it does, is the goal."

---

## 5. System Design

```
 ┌────────────────┐    ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
 │ TRIGGER EVENTS │    │ One Graph  │ │ NotebookLM │ │  Episodic  │ │ Long-term  │
 │  GKE deploys   │    │  topology  │ │  org docs  │ │   memory   │ │   memory   │
 │  Cloud Run     │    │ (planned)  │ │ (planned)  │ │  episodes  │ │ precedents │
 │  Cloud Deploy  │    └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ │  dossiers  │
 │  config/flags  │          │              │              │        └─────┬──────┘
 └───────┬────────┘          └──────────────┴──── advise ──┴──────────────┘
         │ creates                               │  (never decide)
         │ episode                               ▼
         ▼                              ┌────────────────┐
 ┌────────────────┐  opens checkpoint   │  THE REVIEWER  │
 │   THE CLOCK    │ ───────────────────▶│ agent harness  │
 │ dynamic ladder │ ◀─────────────────  │ one session /  │
 │ (policy-owned) │   next check time   │   checkpoint   │
 └────────────────┘                     └───┬────────▲───┘
                                            │        │
                              verdict+record│        │ sealed evidence
                                            ▼        │
 ═════════════════════ TRUSTWORTHY AUTONOMY LAYER ══════════════════════
 ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
 │    EVIDENCE    │ │    VERDICT     │ │   EPISTEMIC    │ │   DRAFT-ONLY   │
 │    SEALING     │ │    RECORDER    │ │    RECORDS     │ │    ACTIONS     │
 │signed envelopes│ │  policy floor  │ │reasoning trail │ │ human approves │
 └────────────────┘ └───────┬────────┘ └────────────────┘ └────────────────┘
                            │ recorded episodes
                            ▼
 ═══════════════════════ ROLLOUT INTELLIGENCE ═══════════════════════════
 ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────────┐
 │  EPISODE   │───▶│  OUTCOME   │───▶│  ACCURACY  │───▶│  PRECEDENTS &  │
 │   STORE    │    │ COLLECTION │    │ SCORECARD  │    │    DOSSIERS    │
 └────────────┘    └────────────┘    └────────────┘    └───────┬────────┘
                     ground truth      falseSafe ·             │
                     (never the        falseHalt               ▼
                     agent's own                     feeds back to the
                     verdicts)                       reviewer as memory
```

### 5.1 Trigger events — everything that changes production

The system consumes a simple event contract: any change event the CD
system posts — GKE deployments, Cloud Run service creations and
updates, Cloud Deploy pipelines (bridged today by a shipped converter),
config and flag pushes — creates an **episode**: an owned,
fingerprinted record of one rollout, with service identity resolved
against the catalog. The reviewer never re-discovers state per session;
the episode is the spine everything else attaches to.

### 5.2 The clock — policy-owned, dynamic

A versioned **policy pack** declares the checkpoint ladder (stages and
offsets), the bounds any schedule change must respect, and the exit
criteria that close a review early. The agent may *propose* the next
check time from evidence ("at this traffic rate, the sample floor lands
in 18 minutes") — tightening is honored, loosening is clamped, and
ending the ladder is never the agent's call. Policies are per
deployment today, with per-application pack selection as configuration
ahead — a payment service and a batch pipeline get the scrutiny cadence
their risk profiles demand. Alert-fired out-of-band checkpoints are a
planned extension of the same contract.

### 5.3 Privileged data sources — what the reviewer knows

Four sources feed the review. All four are **advisory and
trust-graded**: they shape where the agent looks; none can satisfy a
policy rule or soften a verdict — this is the single rule that makes
rich memory safe.

- **Episodic memory** *(shipping)*: the episode store — this rollout's
  prior checkpoints and this service's past episodes, with evidence.
- **Long-term memory** *(shipping)*: labeled precedents (similar
  rollouts *and how they actually turned out*) and per-service
  **dossiers** — durable facts the agent may propose but only humans
  promote, and which reality (an architecture change) automatically
  invalidates.
- **One Graph** *(planned integration)*: the live dependency graph —
  what this service calls, what calls it, what shares its blast radius.
- **NotebookLM** *(planned integration)*: runbooks, design docs,
  postmortems — written organizational memory, queryable at review time.

### 5.4 The reviewer — one agent session per checkpoint

Gather the standard signed evidence bundle, investigate with the data
sources, reason, compose the epistemic record, record the verdict,
propose the next check. The agent runtime is deliberately swappable —
the entire trust architecture lives *around* the agent, not inside its
prompt, which is why the same system has been demonstrated on two
independent runtimes without modification.

### 5.5 The Trustworthy Autonomy layer — why the verdict can be trusted

Technically, the layer is a set of small components flanking the
harness: two sealing servers, a record validator, and a minting proxy
for bring-your-own observability. The harness holds the model; the
components around it hold the trust — and the signing
key never crosses the line between them:

```
                    ┌─────────────────────────────────────────┐    ┌─ VALIDATOR ──────────────────┐
                    │               THE HARNESS               │    │ validate-epistemic-record.py │
┌────────────────┐  │ ┌─ SKILL ─────────┐ ┌─ COMPOSE ───────┐ │    │ ┌─ SCHEMAS ────────────────┐ │
│   THE CLOCK    │  │ │ SKILL.md + nine │ │ epistemic record│ │    │ │ epistemic-record.schema  │ │
│  Cloud Tasks / │  │ │ reference specs │ │ + quoted evid.  │ │self│ │ + $ref sub-schemas       │ │
│  relay         │  │ │ — the protocol  │ │ + draft action  │ ├───▶│ └──────────────────────────┘ │
└───────┬────────┘  │ │ the agent obeys │ │ + next-check    │ │    │ modes: file · --self-test ·  │
        │ REST :7611│ └─────────────────┘ │   proposal      │ │    │ --episode (via intel REST)   │
        │ open ckpt │ ┌─ AGENT ─────────┐ └─────────────────┘ │    │ exit codes 0 / 2-7           │
        │ next_check│ │ MCP client / rr │ ┌─ REPORT ────────┐ │    └──────────────────────────────┘
        │           │ │ CLI bridge      │ │ rollout-report  │ │
        │           │ └─────────────────┘ │ .md + record    │ │
        │           │                     └─────────────────┘ │
        │           └───┬──▲─────────────────┬──▲───────┬──▲──┘
        │ calls         │  │  records/       │  │ seals │  │ BYO seals
        │               │  │  context        │  │       │  │ (corrob.)
        │               │  │                 │  │       └──┼────────────────┐
        │               │  │                 │  │          └────────────────┼──┐
┌───────▼───────────────▼──┴─────────┐   ┌───▼──┴───────────────────┐   ┌───▼──┴──────────────────────┐
│ rollout-intel    :7610 / :7611     │   │ gcp-observe :7600/:7601  │   │ mint-proxy            :7630 │
│ ┌─ TOOLS ─────────────────────┐    │   │ ┌─ TOOLS ────────────────┐ │ │ ┌─ SEAL WRAPPER ──────────┐ │
│ │ get_context_pack ·          │    │   │ │ query_metric ·         │ │ │ │ fronts ANY BYO MCP      │ │
│ │ run_stage_checks ·          │    │   │ │ search_logs ·          │ │ │ │ observability server ·  │ │
│ │ evaluate_policy ·           │    │   │ │ list_services ·        │ │ │ │ seals every result      │ │
│ │ record_checkpoint ·         │    │   │ │ list_assets            │ │ │ │ (corroborating tier)    │ │
│ │ find_similar_episodes ·     │    │   │ ├─ MINT (seal) ──────────┤ │ │ └────────────▲────────────┘ │
│ │ get_dossier ·               │    │   │ │ HMAC · scope ·         │ │ │ ┌────────────┴────────────┐ │
│ │ propose_dossier_update      │    │   │ │ freshness · hash       │ │ │ │ Datadog · Prometheus ·  │ │
│ ├─ IDENTITY ──────────────────┤    │◀──┤ ├─ BUNDLE :7601 ─────────┤ │ │ │ internal MCP servers    │ │
│ │ catalog resolve · confirmed │    │   │ │ server-to-server feed  │ │ │ └─────────────────────────┘ │
│ │ vs candidate                │    │   │ └───────────▲────────────┘ │ └─────────────────────────────┘
│ ├─ VERIFY (seal twin) ────────┤    │   │ ┌───────────┴────────────┐ │
│ │ sig · hash · freshness      │    │   │ │     GCP APIs / SIM     │ │
│ ├─ POLICY FLOOR ──────────────┤    │   │ └────────────────────────┘ │
│ │ SLO rules · ladder · bounds │    │   └──────────────────────────┘
│ ├─ RECORDER ──────────────────┤    │
│ │ tighten-only · scope guard  │    │
│ │ · replay-safe               │    │
│ ├─ CONFIG ────────────────────┤    │
│ │ policy-pack.yaml (versioned)│    │
│ │ · services catalog          │    │
│ └─────────────────────────────┘    │
└───────────┬────────────────────────┘
            │ writes (sole writer)       ┌──────────────────────────────────┐
            ▼                            │ OBS_SIGNING_KEY: held by the     │
┌────────────────────────────────────┐   │ sealing servers ONLY — never the │
│ EPISODE STORE (SQLite · WAL)       │   │ harness: it can carry seals,     │
│ episodes · checkpoints ·           │   │ never make or alter them         │
│ observations · decisions ·         │   └──────────────────────────────────┘
│ outcomes · feedback ·              │
│ dossier_journal · retrieval_audit  │
└────────────────────────────────────┘
```

The division of labor: **gcp-observe** is the trusted witness — it
executes every observability query itself and seals each result at the
moment of collection; the **mint-proxy** extends that witness role to
any bring-your-own observability server, sealing its results as
corroborating-tier evidence. **rollout-intel** is the trusted judge —
it re-verifies every seal, re-runs the deterministic policy, applies
the tighten-only rule, and is the only process that writes the episode
store. The **validator** is the trusted editor — it mechanically checks
that every recorded verdict carries its complete reasoning, both as the
session's own self-check and as an after-the-fact audit against the
recorded episode. The harness between them holds the model, the skill,
and the report — it does the thinking, but it is a courier and an
author, never a witness, a judge, or its own editor.

The layer that turns "the model said so" into "here is the proof":

- **Signed evidence envelopes.** Every observation is sealed at its
  source — tamper-evident, scoped to its service and time window,
  freshness-bounded. The agent carries evidence; it cannot fabricate,
  alter, re-scope, or age it without detection. A minting proxy extends
  the same seal to any bring-your-own observability server (as
  corroborating-tier evidence — policy rules are satisfiable only by
  the typed standard bundle), and harness-level minting seals even raw
  command output.
- **Epistemic records.** A verdict never travels as a bare label. It
  embeds observations (each citing sealed evidence), inferences with
  live alternatives, qualitative confidence with an honest basis,
  explicit unknowns, the checks that could overturn it, and its own
  expiry. Enforced by an in-session self-check and a mechanical
  validator: a verdict cannot pass review without stating its evidence,
  its unknowns, and what would change its mind.
- **The deterministic floor.** Hard SLO rules evaluate independently of
  the model. The recorder re-runs them and **rejects any verdict that
  softens the floor** — the attempt itself is stored for audit.
  Interpretation may only tighten. "Insufficient evidence" is a
  first-class verdict, never rounded up to healthy.
- **Draft-only authority.** Remediation exists only as a structured
  draft naming blast radius and required approvers — in the record
  schema, an executed action is unrepresentable. Autonomy level is
  harness configuration, never agent initiative (see §7).
- **The trust boundary.** Log lines and tool payloads are data, never
  instructions. Injection attempts are quoted verbatim as evidence,
  flagged, and surfaced — an attack on the reviewer becomes a finding
  in the report.

### 5.6 Rollout Intelligence — the compounding loop

Recording is only half the system; the other half grades and learns:

```
 ┌──────────────┐  verdicts + ┌──────────────┐  labels at  ┌──────────────┐
 │ THE REVIEWER │  records    │ EPISODE STORE│  horizons   │   OUTCOME    │
 │ next session │────────────▶│   (SQLite)   │◀────────────│  COLLECTOR   │
 └───▲──────▲───┘             └──────┬───────┘             └──────▲───────┘
     │      │                        │ labeled                       │ reads
     │      │                        │ episodes                      │ truth
     │      │                        ▼                        ┌──────┴───────┐
     │      │              ┌────────────────────┐             │  MONITORING  │
     │      │              │   LABELED CORPUS   │             │   + HUMANS   │
     │      │              └──┬──────┬───────┬──┘             └──────────────┘
     │      │                 │      │       │
     │      │   ┌─────────────┘      │       └────────┐
     │      │   │                    │                │
     │  ┌───┴───▼──────┐   ┌─────────▼─────────┐   ┌──▼────────────────────┐
     │  │ PRECEDENTS   │   │ SUGGESTIONS       │   │ SCORECARD             │
     │  │ rungs · bal- │   │ candidate lessons │   │ falseSafe · falseHalt │
     │  │ ance · arch  │   │ ≥3 labeled        │   │ (verdicts × labels)   │
     │  │ hard-filter  │   │ supporters        │   └───────────┬───────────┘
     │  └──────────────┘   └─────────┬─────────┘               │ promotes /
     │                               │                         │ demotes
     │  ┌──────────────┐   ┌─────────▼─────────┐               ▼
     └──┤   DOSSIER    │◀──│  HUMAN PROMOTION  │        THE AUTONOMY DIAL
        │ typed claims │   │ (approve/reject)  │             (see §7)
        └──────▲───────┘   └───────────────────┘
               │ expires stale claims
        ┌──────┴───────┐
        │ ARCH CHANGE  │
        │ (from deploy │
        │   events)    │
        └──────────────┘
```

Every arrow is a hand-off between authorities: the reviewer writes
verdicts but never labels; monitoring and humans write labels but never
verdicts; the corpus admits only labeled episodes; suggestions reach
the dossier only through human hands; and the scorecard — verdicts
settled against labels — is what moves the autonomy dial. In detail:

- **Outcome collection.** At policy-defined horizons, ground truth is
  gathered from monitoring and humans — *never* from the agent's own
  verdicts — and each episode is labeled healthy / regressed /
  rolled-back.
- **The accuracy scorecard.** Labels × verdicts yield the two numbers
  that matter: **falseSafe** (said healthy, was regressed — the
  dangerous one) and **falseHalt** (cried wolf — the trust-eroding
  one). The reviewer is a measured instrument with a published error
  rate.
- **Precedents & dossiers.** The labeled corpus feeds retrieval (with
  scope-widening and architecture filters); durable learnings flow
  through the human-governed dossier.
- **Scoring.** Independent per-principle rubrics grade every execution,
  so trustworthiness itself is a tracked, trending metric.

---

## 6. Preventative vs Reactive

Every rollout safety mechanism sits somewhere on a timeline relative to
the failure it addresses. **Reactive** mechanisms learn after users pay;
**preventative** mechanisms act before exposure. The design goal is not
to pick one — it is to walk the whole timeline leftward, phase by
phase, and to make the reactive side *fund* the preventative side with
data.

| Rollout phase | What can go wrong here | Reactive answer (industry) | What Rollout Reviewer does |
|---|---|---|---|
| **Pre-ship** | Risky change shapes: config flips, dependency bumps, schema changes | Nothing — risk is invisible until traffic | Risk-shaped scrutiny; simulated tomorrows (Fast-Forward) |
| **Ramp (canary)** | Immediate regressions: error spikes, latency breaches | Static canary analysis; a human glancing | Evidence-based checkpoint verdicts with causal chains, minutes in |
| **Soak** | Delayed failures: leaks, retry amplification, slow-burn creep | The 3 a.m. page | Stability analysis at later checkpoints; validity horizons that expire verdicts honestly |
| **Steady state** | The *next* rollout repeating history | Postmortems that decay in docs | Outcome grading → precedents, dossiers, sharper policies |

**What reactive maturity buys — and its ceiling.** Alerts, on-call,
rollback, postmortems: essential, and permanently insufficient, because
the cost is already paid when they fire. The reviewer's first
contribution is making the reactive side *fast and explainable*:
detection compressed into the canary window, every catch arriving with
its causal chain and evidence, every miss measurable. That alone
converts incidents from hours of exposure into minutes.

**The preventative family.** Prevention is not one feature; it is a set
of concepts that all consume the same substrate — the labeled,
evidence-sealed episode corpus:

- **Risk-shaped exposure.** Not every change deserves the same ramp.
  Precedent history and change classification let the policy ladder
  itself adapt *before* the rollout: a change shaped like past
  regressions gets more checkpoints, tighter intervals, slower
  exposure; a routine change earns a lighter ladder. Prevention here is
  simply scrutiny applied where history says it belongs.
- **Simulated tomorrows — Rollout Fast-Forward.** Some failures only
  surface at operational ages a canary never reaches: the connection
  pool that leaks over six hours, the retry storm that needs peak
  traffic, the certificate that expires Sunday. Fast-Forward (core
  implemented) compiles a change set into ranked delayed-failure
  hypotheses, probes them within an experiment budget, and emits either
  a **replayable temporal counterexample** or an explicitly qualified
  all-clear — a review of the rollout's future, held to the same
  evidence-integrity standard as reviews of its present.
- **Blast-radius awareness** *(with One Graph)*: knowing what shares
  fate with this service turns "is this service healthy?" into "what
  did this rollout put at risk?" — and can hold a ramp before a shared
  dependency is exposed.
- **Institutional pre-checks** *(with NotebookLM + dossiers)*: the
  system reads the service's own history before the ramp — "the last
  three regressions here were config-shaped; this is a config push" —
  and front-loads exactly those checks.
- **The learning loop as the engine.** This is the deliberate
  architecture point: every reactive catch becomes preventative
  material. A caught regression becomes a labeled episode; labeled
  episodes become precedents and priors; recurring causes become
  dossier facts and, when humans agree, policy rules. **Reactive
  operation is how the preventative system is trained** — the two are
  one pipeline, not two products.

**The honest boundary.** Preventative signals are forecasts, and the
system never lets a forecast masquerade as an observation: predictions
are advisory, labeled as simulation- or history-derived, and only live
evidence gates live traffic. Prevention narrows what reaches
production; it never manufactures certainty about it.

---

## 7. The Autonomy Dial — Launching as a Trust Progression

The final design question is not *can* the agent act autonomously — it
is *how an organization comes to let it*. Our answer: autonomy is a
**dial, not a switch**, and the dial is moved by measured evidence,
never by the agent. This is a structural property (the agent's
authority posture is harness configuration; its remediation is
draft-only by schema), which means the launch plan and the trust model
are the same document:

**Stage 1 — Reason (observer).** The reviewer runs alongside the human
engineer on every rollout. It gathers evidence, reasons, and records
full verdicts — but they are annotations beside the human's decision,
gating nothing. This stage looks humble and is doing the heaviest
lifting: every verdict is being graded against reality, building the
falseSafe/falseHalt scorecard, and every episode grows the corpus.
The human's cost doesn't drop much yet; the *organization's evidence
about the reviewer* compounds daily.

**Stage 2 — Augment (first reader).** The reviewer becomes the first
reader of every rollout; the human becomes the approver. A healthy
verdict arrives pre-assembled — evidence, reasoning, unknowns — and
confirming it takes a minute, not thirty. A regression-suspected
verdict arrives with the causal chain and a draft remediation awaiting
approval. Human attention collapses onto exceptions. Promotion into
this stage is not a judgment call: it is the Stage-1 scorecard clearing
agreed thresholds.

**Stage 3 — Control (gated autonomy).** For rollout classes where the
scorecard has stayed above the bar — falseSafe below the agreed ceiling
over enough labeled episodes, trustworthiness scores sustained — the
reviewer's healthy verdict advances the ramp on its own, and humans see
only flagged rollouts. Remediation remains draft-only or graduates to
pre-approved runbooks; the agent never acquires authority the harness
was not explicitly configured to grant.

Three properties make this progression something an organization can
actually sign:

1. **Promotion is earned per class, by numbers.** Not "we trust it
   now," but "on this rollout class, over N labeled episodes, falseSafe
   is X and falseHalt is Y — the bar we pre-agreed is met." Different
   services move at different speeds; a payment service may sit at
   Stage 2 while internal tools run at Stage 3.
2. **Demotion is automatic.** The same metrics that promote also
   demote: if accuracy regresses, the class drops a stage without a
   meeting. The dial moves on evidence in both directions — which is
   precisely what makes moving it up defensible.
3. **Nothing changes but who acts.** The records, the sealed evidence,
   the audit trail, the floor — identical at every stage. Promotion
   never reduces what is known or provable about a review; it only
   changes whether a human must act on it. There is no trust cliff to
   fall off, because trust was never asked for — it was measured.

**The point, landed:** we do not ask the organization to trust an
agent. We ask it to read a scorecard the agent cannot forge — and to
pre-agree on what the numbers must say before the dial moves.
