# Rollout Reviewer

### Trustworthy Autonomous Cloud Operations on the Ensemble Platform

---

> **The one-sentence version:** We sell the control structure that makes an
> autonomous rollout reviewer *trustworthy* — not just capable — and the
> only moat we claim is the one the outcome data keeps proving.

---

## How to Read This Document

This document serves three audiences at three depths:

| You are a… | Start here | Time |
|---|---|---|
| **Executive or PM** | [Executive Summary](#executive-summary), then skim the bold text and tables throughout. Read [Value by Persona](#value-by-persona) and [Product Roadmap](#the-next-four-quarters). | ~15 min |
| **Engineer or architect** | Read end to end. The nine principles ([Part II](#part-ii--nine-principles-of-trustworthy-autonomy)) and ten tenets ([Part III](#part-iii--the-rollout-reviewer-principles-applied)) are the technical core. | ~45 min |
| **Security, compliance, or risk** | [Executive Summary](#executive-summary) → [Trust Boundary (P5)](#principle-5--inputs-require-a-trust-boundary) → [Gap Register](#the-gap-register) → [Autonomy Gates](#autonomy-expansion-gates). | ~20 min |

Every real-world claim below survived an independent fact-check. Every
"the system does X today" claim cites a mechanism that exists in the
repositories. Aspiration is labeled as roadmap, never narrated as
implementation. The full adversarial review record is in
[04-independent-critique.md](../principles/04-independent-critique.md).

### Table of Contents

- [Executive Summary](#executive-summary)
- [Part I — The Foundation](#part-i--the-foundation)
  - [The Central Claim](#the-central-claim)
  - [The Intellectual Inheritance](#the-intellectual-inheritance)
- [Part II — Nine Principles of Trustworthy Autonomy](#part-ii--nine-principles-of-trustworthy-autonomy)
  - [P1: Verdicts Require Epistemics](#principle-1--verdicts-require-epistemics)
  - [P2: Evidence Requires Provenance](#principle-2--evidence-requires-provenance)
  - [P3: State Requires Ownership](#principle-3--state-requires-ownership)
  - [P4: Autonomy Requires a Dial](#principle-4--autonomy-requires-a-dial)
  - [P5: Inputs Require a Trust Boundary](#principle-5--inputs-require-a-trust-boundary)
  - [P6: Knowledge Requires a Clock](#principle-6--knowledge-requires-a-clock)
  - [P7: Delegation Requires Ceilings](#principle-7--delegation-requires-ceilings)
  - [P8: Failure Requires a Ladder](#principle-8--failure-requires-a-ladder)
  - [P9: Learning Requires Outcomes](#principle-9--learning-requires-outcomes)
  - [The Review Card](#the-review-card)
  - [Composition — The Principles as a Control Structure](#composition--the-principles-as-a-control-structure)
- [Part III — The Rollout Reviewer: Principles Applied](#part-iii--the-rollout-reviewer-principles-applied)
  - [What the Reviewer Is](#what-the-reviewer-is)
  - [Ten Operating Tenets](#ten-operating-tenets)
  - [The Contribution Contract](#the-contribution-contract)
  - [Autonomy Expansion Gates](#autonomy-expansion-gates)
- [Part IV — Value and Competitive Position](#part-iv--value-and-competitive-position)
  - [The Buyer's Question](#the-buyers-question)
  - [The Commodity Baseline](#the-commodity-baseline)
  - [Two Products, One Control Structure](#two-products-one-control-structure)
  - [The Moat Stack](#the-moat-stack)
  - [The Outcome Flywheel](#the-outcome-flywheel)
  - [Value by Persona](#value-by-persona)
  - [Prove It: The Three-Arm Baseline](#prove-it-the-three-arm-baseline)
  - [Erosion Risks, Owned](#erosion-risks-owned)
- [Part V — The Road Ahead](#part-v--the-road-ahead)
  - [The Gap Register](#the-gap-register)
  - [The Next Four Quarters](#the-next-four-quarters)
- [Appendix A — Objections, Honestly Handled](#appendix-a--objections-honestly-handled)
- [Appendix B — References and Further Reading](#appendix-b--references-and-further-reading)

---

## Executive Summary

An autonomous agent is a system that **converts uncertain evidence into
consequential action under delegated authority**. Capability answers "can
it do the job?" Trustworthiness answers a harder question: **"what happens
when it is wrong?"**

The Rollout Reviewer is an autonomous agent that evaluates production
rollouts — inspecting metrics, logs, and service state to determine
whether a deployment is healthy, shows signs of regression, or lacks
sufficient evidence to judge. It runs on the **Ensemble** agent platform,
which provides the governance infrastructure: immutable versioned
registries, capability-bounded tool access, deterministic policy
evaluation, signed evidence chains, and outcome-driven experimentation.

**What makes this system different is not the model. It is the control
structure around the model.**

Nine principles — inherited from epistemology, cybernetics, and safety
science — define what "trustworthy" means for an autonomous agent. Each
principle is a cut-point in the failure chain that runs from poisoned
input to repeated confident failure:

> poisoned input → stale knowledge → unsupported verdict → unverifiable
> evidence → unowned state → unbounded action, amplified by unbounded
> delegation → cliff-edge failure → unlabeled outcome → the same failure
> again, now with more confidence

The Rollout Reviewer translates these nine principles into ten
operating tenets — each enforced by a named mechanism in the platform,
not by a prompt that says "please be careful." The deterministic policy
floor cannot be argued down by the model. Evidence is HMAC-signed and
scope-verified. State lives in an append-only episode store the agent
cannot directly write. Autonomy is a spec field, not a personality
trait. And outcomes grade the system — not demos, not rubric scores, not
vibes.

**The commercial thesis follows directly:** a reviewer that is a prompt
over dashboards sits entirely inside the commodity set (frontier models,
MCP connectors, narrative generation). The moat lives in the layers a
prompt cannot carry — **evidence provenance, durable state, deterministic
policy, outcome labels, and governed workflow** — and it compounds
through a flywheel where every review becomes a labeled episode, every
labeled episode feeds calibration, and calibration evidence is the
currency that purchases autonomy expansion.

The honest position: layers 3 (authority control plane) and 4 (outcome
flywheel) are the differentiated core today; layer 1 (context graph) is
the roadmap bet; layers 2 and 5 are connective tissue being thickened.
Nine gaps are documented by name. The model is a replaceable part — and
that is a feature, not a limitation.

---

## Part I — The Foundation

### The Central Claim

An autonomous agent is a system that **converts uncertain evidence into
consequential action under delegated authority**. Every word is
load-bearing:

- **Uncertain evidence** — the agent never has the world, only
  measurements of it, taken at some time, through some instrument, with
  some coverage.
- **Consequential action** — its outputs change things: deployments
  pause, people get paged, money moves, conclusions enter records that
  outlive the conversation.
- **Delegated authority** — someone lent it power, and that someone
  remains accountable. Delegation without a contract is abdication.

Capability answers "can it do the job?" Trustworthiness answers the
question that matters more: **"what happens when it is wrong?"** — because
it *will* be wrong, and a system that is wrong *safely, legibly, and
recoverably* is categorically different from one that is wrong silently.

The source standard compresses this into a failure chain. Extended to
cover the full principle set:

```
poisoned or in-band input
  → stale knowledge
    → unsupported verdict
      → unverifiable evidence
        → unowned state
          → unbounded action, amplified by unbounded delegation
            → cliff-edge failure
              → unlabeled outcome
                → the same failure again, now with more confidence
```

**Each of the nine principles below is a cut-point in that chain.** None
of this is novel; that is precisely its strength. We are inheriting three
centuries of epistemology, eighty years of control theory, and fifty
years of safety science. The failure modes of autonomous agents are not
new failure modes — they are old ones wearing a new interface.

### The Intellectual Inheritance

Three older disciplines already solved large parts of this problem. We
cite them not for decoration but because each supplies a working tool.

#### Epistemology — The Discipline of Justified Belief

The traditional analysis of knowledge as *justified true belief* — often
traced to Plato — was famously dismantled by Edmund Gettier's 1963
counterexamples
([Analysis, 23(6)](https://doi.org/10.2307/3326922)),
which showed that justification, truth, and belief can all be present
while knowledge is absent: you can be right by accident. That is exactly
the production incident that outcome-labeling catches: the reviewer said
"healthy," the rollout was healthy, and the verdict was still *lucky*
because the discriminating evidence was never examined.

C.S. Peirce's *abduction* — hypothesis generation, roughly what later
philosophy calls inference to the best explanation — is the formal name
for what a diagnostician does. Karl Popper's *falsification* teaches
that a hypothesis earns standing only by surviving attempts to kill it,
which is why a verdict must ship with its **discriminating checks**: the
observations most likely to overturn it. Bayesian updating supplies the
arithmetic of changing one's mind, and David Hume's problem of induction
is the polite reminder that "it held for the last hour" never *entails*
"it holds now" — the floor under every **decision horizon** in this
document.

#### Cybernetics — The Discipline of Regulation

W. Ross Ashby's law of requisite variety — in his own words, "only
variety can *destroy* variety"
([Introduction to Cybernetics, 1956](https://archive.org/details/introductiontocy00ashb))
— means a controller must have at least as many distinguishable responses
as the disturbances it must counter. An agent with one response ("looks
fine") cannot regulate a production system with a thousand failure modes.

Roger C. Conant and Ashby sharpened it in 1970 with the theorem that is
also their paper's title: **"Every good regulator of a system must *be* a
model of that system"**
([Int. J. Systems Sci., 1(2)](https://doi.org/10.1080/00207727008920220)).
An agent without an explicit world model — topology, ownership, change
history — is not regulating; it is reacting.

#### Safety Science — The Discipline of Organized Failure

Charles Perrow's *Normal Accidents*
([1984, Basic Books](https://press.princeton.edu/books/paperback/9780691004129/normal-accidents))
argued that systems combining **interactive complexity** with **tight
coupling** produce accidents as a normal property, not an anomaly — and
an LLM agent wired into production tooling is both interactively complex
and tightly coupled by construction.

High-reliability-organization research
([Weick & Sutcliffe, *Managing the Unexpected*](https://www.wiley.com/en-us/Managing+the+Unexpected%3A+Sustained+Performance+in+a+Complex+World%2C+3rd+Edition-p-9781118862414))
catalogs the practices of organizations that defy Perrow's odds —
carrier decks, air-traffic control — and its five habits read like an
agent spec: preoccupation with failure, reluctance to simplify,
sensitivity to operations, commitment to resilience, deference to
expertise.

Jens Rasmussen's drift model
([Safety Science, 27(2-3), 1997](https://doi.org/10.1016/S0925-7535(97)00052-0))
warns that systems migrate toward the boundary of acceptable performance
under efficiency pressure — autonomy granted *will* be autonomy leaned
on.

And Nancy Leveson's STAMP
([*Engineering a Safer World*, MIT Press, 2011](https://direct.mit.edu/books/book/2908/Engineering-a-Safer-World))
reframes the whole problem: **accidents are not component failures; they
are control-structure failures** — inadequate constraints on a system
whose components all "worked." That is the deepest justification for
this document: the model is a component; trustworthiness is a property
of the control structure around it.

#### Double-Entry Bookkeeping

One more inheritance deserves naming because it is five centuries old and
still in production. Luca Pacioli codified double-entry bookkeeping in
1494 from older Venetian practice. Every entry has a counterpart; the
books must balance; fraud and error surface as violated invariants. It is
the oldest deployed system of machine-checkable provenance — and the
intuition behind evidence ledgers and idempotent report generation.

---

## Part II — Nine Principles of Trustworthy Autonomy

The first four are the source standard's, deepened. The following five
are what **operating** agents in an adversarial, temporal, consequential
environment forces into existence — only one of them (delegation) waits
for a platform of many agents; the rest bite the very first reviewer you
ship.

Each principle gets the same treatment: **the claim**, the
**philosophical root**, **real-world evidence**, the **translation** to
agent systems, and **the test** a reviewer should apply.

---

### Principle 1 — Verdicts Require Epistemics

> **A conclusion without its justification structure is not knowledge; it
> is a guess with confidence-colored paint.**

**Root.** The observed/inferred distinction is the oldest tool in
epistemology, and the most commonly dropped in production. A verdict is a
compressed claim; epistemics is the decompression algorithm: what was
seen, what was concluded, how strongly, what is missing, what would
change the answer.

**Case: Three Mile Island (1979).** A pilot-operated relief valve stuck
open, draining coolant. The control-room indicator did not show the
valve's *position* — it showed that the close command had been *sent*.
The operators read an inference ("we commanded it closed") as an
observation ("it is closed") and spent over two hours fighting the wrong
failure. The instrument did not lie; the interface collapsed the
epistemic distinction between commanded state and actual state. Most
agent hallucination incidents are exactly this shape: an inference
presented in the grammatical form of an observation.

> *Sources:*
> [NRC TMI-2 Lessons Learned Task Force Report (NUREG-0585)](https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr0585/),
> [Kemeny Commission Report (1979)](https://www.threemileisland.org/resource/248.htm)

**Case: Air France 447 (2009).** Iced-over pitot tubes fed the autopilot
inconsistent airspeed; the automation disengaged and handed a
suddenly-degraded information environment to a crew given no structured
account of *what the system no longer knew*. **Uncertainty must be handed
over explicitly**, because the consumer of a verdict inherits its blind
spots.

> *Source:*
> [BEA Final Report, July 2012](https://www.bea.aero/en/investigation-reports/notified-events/detail/event/accident-to-the-airbus-a330-203-registered-f-gzcp-operated-by-air-france-on-1st-june-2009-in-t/)

**Translation.** An agent's assessment is a structured object, not a
sentence: observations (with evidence references), inferences (marked as
such, with the observations they depend on), calibrated confidence,
enumerated unknowns, surviving alternative hypotheses, the discriminating
checks that would settle them, and a validity horizon. Abstention —
"insufficient evidence" — is a first-class verdict, and the selective
prediction literature treats it as exactly that: a managed
risk-coverage trade-off, not a failure. Confidence must be a measured
quantity, not a linguistic register; an uncalibrated "0.92" is
confidence theater.

> **The test:** Ask of any verdict: *"What would change your mind?"* If
> the system cannot answer, it does not hold a belief; it holds a slogan.

---

### Principle 2 — Evidence Requires Provenance

> **A claim you cannot trace is a rumor, no matter how quantitative it
> looks.**

**Root.** Courts developed chain of custody, science developed methods
sections and citation, accounting developed the audit trail — three
independent traditions converging on the same invariant: **the value of
evidence is inseparable from the record of where it came from and what
was done to it.** The
[W3C PROV](https://www.w3.org/TR/prov-overview/) data model gives this a
formal structure (entities, activities, agents, derivations);
content-addressed storage (the mechanism inside git) gives it an
immutability primitive.

**Case: The British Post Office Horizon Scandal (1999–2024).** Arguably
the largest provenance failure in legal history. Between 1999 and 2015,
more than nine hundred subpostmasters were prosecuted for theft and false
accounting based on shortfalls reported by the Horizon accounting system.
The evidence *looked* quantitative — ledgers, balances, precise sums —
and courts operated on a presumption that computer records were reliable.
The system had known defects; remote-access modifications to branch
accounts were possible and initially denied. Convictions began to be
overturned in late 2020, the landmark Court of Appeal ruling followed in
2021, and the scale of the injustice ultimately required statutory mass
exoneration in 2024.

Numbers without lineage did not merely mislead — they imprisoned people.

> *Sources:*
> [Williams Inquiry (ongoing)](https://www.postofficeinquiry.org.uk/),
> [Hamilton & Others v Post Office Ltd \[2021\] EWCA Crim 577](https://www.judiciary.uk/judgments/hamilton-others-v-post-office-ltd/)

When an agent's report says "error rate rose to 2.4%," the difference
between evidence and Horizon is: source system, exact query, time
window, retrieval timestamp, transformation history, coverage, and an
immutable reference.

**Translation.** Two mechanisms matter beyond the provenance envelope
itself. First, **epistemic laundering**: multi-step agent workflows
summarize summaries, and a hedged observation becomes a confident "fact"
three artifacts downstream unless claims carry their identifiers,
confidence, and caveats *through* every summarization. Second,
**authenticated evidence**: in adversarial environments, provenance must
be cryptographic, not conventional — evidence signed at the source,
scoped to the subject under review, verified at use.

> **The test:** Pick any number in the report and ask: *"Show me the
> query, the window, and the snapshot."* If reproducing the claim
> requires trusting the agent's memory, there is no claim — only prose.

---

### Principle 3 — State Requires Ownership

> **Persistent facts without an authoritative owner converge on fiction.**

**Root.** Distributed-systems theory has spent fifty years on exactly
this: Leslie Lamport taught us that "what happened when" is not free in a
distributed world; consensus protocols exist because *somebody must be
authoritative* about shared state; event sourcing and durable-execution
engines exist because reconstructing truth from an append-only history
beats trusting a mutable snapshot.

**Case: Knight Capital (August 1, 2012).** A deployment reused an old
feature flag whose previous meaning — a defunct trading function unused
since about 2003, known internally as Power Peg — was still wired into
dormant code, and the rollout reached only seven of eight servers. The
eighth server interpreted the repurposed flag under its old semantics and
fired orders continuously: roughly $440 million lost in about 45 minutes
(the firm's reported pre-tax figure; the SEC's order puts it above $460
million), ending the company's independence. Every layer of the failure
is a state-ownership failure: a flag whose *meaning* had no owner, a
deployment whose *completeness* was not a reconciled fact, and semantics
that had silently decayed for nine years.

> *Source:*
> [SEC Administrative Proceeding File No. 3-15570](https://www.sec.gov/litigation/admin/2013/34-70694.pdf)

**Case: GitLab (January 31, 2017).** An engineer, fatigued and fighting
replication lag, ran a destructive removal on what he believed was the
failing secondary database — it was the primary. Five separate backup
mechanisms then turned out to be broken or misconfigured; roughly six
hours of production data were lost. "Which server am I on" and "do the
backups actually restore" were state nobody authoritatively owned — they
were assumptions.

> *Source:*
> [GitLab.com Database Incident Postmortem](https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/)

**Translation.** Every persistent field in an agent system needs an
owner, a version, a lifecycle, and a conflict policy. The agent's report
is a **projection** of operational state, never the source of truth.
Writes are versioned (compare-and-swap, not last-writer-wins), terminal
states actually terminate, and memory that agents *propose* into is
segregated from memory that has been *promoted* by an authority.

> **The test:** For any fact the system remembers, ask: *"Who is allowed
> to change this, and how would we detect a stale write?"* If the answer
> is "whoever wrote last," you have a rumor mill with persistence.

---

### Principle 4 — Autonomy Requires a Dial

> **Authority must be action-specific, risk-priced, and revocable — an
> all-or-nothing agent is a loaded institution-shaped object.**

**Root.** Parasuraman, Sheridan, and Wickens
([IEEE Trans. SMC, 2000](https://doi.org/10.1109/3468.844354))
modeled automation as *degrees* across information acquisition, analysis,
decision selection, and action implementation — not a binary. SAE J3016's
six levels of driving automation
([SAE International, 2021](https://www.sae.org/standards/content/j3016_202104/))
made graduated autonomy a household concept. The dial is not bureaucracy;
it is the requisite-variety response to the fact that different actions
carry wildly different blast radii and reversibility.

**Case: Boeing MCAS (2018–2019).** A flight-control function was granted
large, *repeating* authority over the horizontal stabilizer on the
evidence of a **single angle-of-attack sensor**, with no crew-facing
disclosure of the new authority and no intuitive dial to step it down.
Two crashes — Lion Air 610 (October 2018) and Ethiopian 302 (March 2019)
— and a roughly twenty-month grounding followed. Every ingredient of the
anti-pattern: high-authority action, low-quality evidence, no epistemic
humility at the sensor boundary, no graduated fallback, and an
interaction model the human operators had not been told about.

> *Source:*
> [Joint Authorities Technical Review (JATR) Report, October 2019](https://www.faa.gov/news/media/attachments/Final_JATR_Submittal_to_FAA_Oct_2019.pdf)

**Counter-case: Apollo 11 (July 1969).** Minutes from the lunar surface,
the guidance computer flooded with 1201/1202 executive alarms — a
radar-interface fault was stealing compute cycles. The system had been
*designed* with priority-based scheduling: it shed low-priority tasks and
kept flying the critical ones, and mission control, drilled on exactly
this failure signature, called "GO." That is the dial working: bounded
degradation instead of binary failure, plus humans who had rehearsed the
boundary.

> *Source:*
> [NASA Mission Report, Apollo 11](https://www.hq.nasa.gov/alsj/a11/a11.1202.html)

**Case: AWS S3 (February 28, 2017).** An authorized operator running an
established playbook mistyped one input and removed far more capacity
than intended, taking down S3 in us-east-1 for hours and much of the
internet with it. The fix was not "train harder" — it was to change the
tool so it could not remove capacity below a safety floor, or too much
too fast. **Even human authority needs the dial**; blast-radius limits
belong in the tool, not the intention.

> *Source:*
> [AWS Summary of the Amazon S3 Service Disruption](https://aws.amazon.com/message/41926/)

**Translation.** Every tool call an agent can make gets an explicit
autonomy level — observe, analyze, recommend, prepare,
execute-with-approval, execute-within-policy — assigned by risk,
reversibility, confidence, environment, and blast radius, and *enforced
structurally* (the tool surface simply lacks the mutating verb; the
credential lives elsewhere; the permission is "ask") rather than
rhetorically (a prompt that says "please be careful"). Corrigibility is
part of the contract: a human stop must always win.

> **The test:** For each action: *"What is the worst thing this can do at
> this level, and who signed up for that?"* If nobody signed up
> explicitly, the dial is set wrong.

---

### Principle 5 — Inputs Require a Trust Boundary

> **The context window is a data channel. Command authority never arrives
> in-band.**

**Root.** This is the oldest sin in computing wearing a new coat:
in-band signaling. Phone phreaking existed because the telephone network
carried control tones in the same channel as voice; SQL injection existed
because queries and data shared a string; and prompt injection exists
because an LLM's context window is one undifferentiated channel in which
evidence, instructions, and attacker text are typographically identical.

**Evidence.** This principle's flagship evidence is **structural rather
than actuarial** — the argument is deductive. Simon Willison's "lethal
trifecta" formulation is the crispest: an agent combining (a) access to
private data, (b) exposure to untrusted content, and (c) the ability to
externally communicate (our extension: any action channel) is exploitable
*by construction* unless the trust boundary is engineered. A production
reviewer reads logs — attacker-writable by definition, since anyone who
can trigger an error writes to your logs — holds privileged evidence
access, and files reports humans act on: all three legs, every session.

The supply-chain record supplies adjacent actuarial evidence: the XZ
Utils backdoor
([March 2024](https://www.openwall.com/lists/oss-security/2024/03/29/4))
and SolarWinds
([2020, CISA](https://www.cisa.gov/news-events/news/joint-statement-federal-bureau-investigation-fbi-cybersecurity-and-infrastructure-security))
were trusted *channels* carrying untrusted content — trust assigned to
the pipe rather than verified on the artifact.

**Translation.** Quoted content stays quarantined — log lines, metric
labels, and tool payloads are displayed as evidence, never obeyed as
directives. Evidence channels are authenticated and scoped (P2). And one
attack the integrity framing misses: **availability**. In a tighten-only
system (see T1), an attacker who controls log content can inject
regression-shaped evidence or starve the evidence channel, weaponizing
the system's conservatism into a deployment denial-of-service. The
defense: adversarial tightening is itself a detectable signature that
pages a human.

> **The test:** *"If an attacker authored every input this agent reads,
> what is the worst outcome a consumer of its output would act on?"*

---

### Principle 6 — Knowledge Requires a Clock

> **Every fact the agent holds was true *as of some moment*, and decays;
> reasoning that ignores time-correctness is reasoning about a world that
> no longer exists.**

**Root.** Finance and law solved this with **bitemporality**: *valid
time* (when the fact was true in the world) versus *record time* (when
the system learned it). An assessment made at 14:32 about the window
14:00–14:30 using topology observed at 10:16 is a three-clock object,
and collapsing those clocks is how systems confidently describe
yesterday.

**Why separate billing.** Time-correctness could be distributed as
clauses of P1 (horizons), P2 (windows), and P3 (versioned state) — and
that is exactly how it gets lost: a cross-cutting concern distributed
across three owners has none. Staleness arrives *silently*: nothing
errors when you consult a current-state graph about a last-week
checkpoint. Knight Capital (P3) is also here: the flag's meaning was
true as of 2003, and for nine years no clock recorded its decay.

**The pattern, honestly marked.** Every operator has lived this: the
dependency graph consulted as-of-now to explain an incident under last
week's topology; the 3 a.m. baseline compared against a 9 a.m. treatment
window and reported as a regression (a seasonality error, not a finding);
feature flags and configuration changing behavior between binary
releases, so that "nothing was deployed" and "nothing changed" quietly
stop being synonyms.

**Translation.** Topology, ownership, dependency, and exposure facts
carry validity intervals, observation timestamps, sources, confidence,
and coverage — a current-state answer is *wrong* for a historical
question. Memory follows the same law: what the system learned about a
service last quarter is a *prior*, timestamped and decaying, never a
current observation. Every verdict states how long it should be believed.

> **The test:** For any fact in the context: *"As of when? Learned when?
> Still valid on what assumption?"* Three timestamps or it is folklore.

---

### Principle 7 — Delegation Requires Ceilings

> **A fleet of small, individually reasonable decisions is one large
> decision wearing camouflage — authority must attenuate down the tree
> and be priced in aggregate.**

**Root.** Organizational theory contributes subsidiarity and
span-of-control; resilience engineering contributes bulkheads. Half of
this principle is P4 applied recursively — every delegatee gets a dial,
set no looser than the delegator's. The half that is *new* is the
portfolio view: the question is never only "is this action safe?" but
**"are a thousand of these actions, correlated, safe?"** — because
errors delegated in parallel do not diversify; they synchronize.

**Case: The Morris Worm (1988).** Its author *included* a limiting
mechanism — a probabilistic rule meant to prevent runaway reinfection —
and tuned it wrong; reproduction pressure alone overwhelmed a meaningful
fraction of the then-internet (the conventional estimate is on the order
of a tenth of connected hosts). It remains the cleanest demonstration
that in self-amplifying systems, the *aggregate* behavior is the system.

> *Source:*
> [Spafford, E.H. "The Internet Worm Program: An Analysis." Purdue Technical Report CSD-TR-823, 1988](https://docs.lib.purdue.edu/cstech/714/)

**Translation.** Child agents inherit *subsets*: tools no broader than
the parent's, network policy no looser, budgets as fractions that sum
below the parent's ceiling, depth and concurrency capped. Spawn briefings
are self-contained contracts (task, boundary, termination condition,
reporting format) because a child does not share the parent's context.
Aggregate exposure is a first-class number with an owner.

> **The test:** *"Can any path through the delegation tree end with more
> authority than the root was granted — and what is the fleet's worst
> correlated hour?"*

---

### Principle 8 — Failure Requires a Ladder

> **Systems should degrade by shedding the optional to protect the
> essential — and every recovery path must survive the failure it exists
> to fix.**

**Root.** Fail-closed versus fail-open is a *consequence-asymmetry*
decision: a door lock fails open (people outrank property); a bank vault
fails closed. Erik Hollnagel's Safety-II
([2014, Ashgate](https://www.routledge.com/Safety-I-and-Safety-II-The-Past-and-Future-of-Safety-Management/Hollnagel/p/book/9781472423085))
adds the positive corollary: systems mostly succeed *because* humans and
mechanisms adapt at the boundaries, so design the adaptations.

**Case: Cloudflare (July 2, 2019) and CrowdStrike (July 19, 2024).**
The same lesson, five years apart, from opposite directions. Cloudflare:
a WAF rule containing a catastrophic-backtracking regex was pushed
globally through a fast path that — unlike the standard deployment path —
bypassed staged rollout; CPU exhausted planet-wide within seconds.
CrowdStrike: a content update — a channel file, not a binary — carried a
defect past a validator bug and deployed globally in one step,
blue-screening roughly 8.5 million Windows machines and disrupting
flights, hospitals, and banks. **The fast path is part of the system.**
Every change channel — rules, flags, content, config — needs the same
ladder as the slow path.

> *Sources:*
> [Cloudflare Outage Postmortem](https://blog.cloudflare.com/cloudflare-outage/),
> [CrowdStrike Preliminary Post Incident Review](https://www.crowdstrike.com/blog/falcon-content-update-preliminary-post-incident-report/)

**Case: Meta (October 4, 2021).** A maintenance command withdrew the
backbone, DNS became unreachable, and — the structural lesson — the
recovery tooling, and reportedly even building badge access, depended on
the network that was down. Roughly six hours, in part because the paths
meant to fix the system lived inside the failure domain.

> *Source:*
> [Meta Engineering Blog: More Details on the October 4 Outage](https://engineering.fb.com/2021/10/05/networking-traffic/outage-details/)

**Translation.** An agent's failure ladder is explicit: full function →
reduced evidence (declare coverage gaps, widen uncertainty, prefer
abstention) → advisory-only (verdicts flow, actions do not) → safe stop
(state persisted, episode intact, human notified). And the degraded modes
are *rehearsed* — an untested fallback is a rumor about a safety property
(GitLab's five broken backup mechanisms, again).

> **The test:** *"Show me the second-worst mode."* Systems with only two
> modes — perfect and catastrophic — have chosen catastrophe as their
> fallback.

---

### Principle 9 — Learning Requires Outcomes

> **A system that never checks its verdicts against reality is not
> learning; it is accumulating folklore with a database.**

**Root.** Goodhart's law (in Marilyn Strathern's phrasing: when a measure
becomes a target, it ceases to be a good measure) governs any system
graded on proxies. The machine-learning literature adds two sharp
warnings: hidden feedback loops, where a model trained on outcomes it
influenced launders its own biases into "ground truth"
([Sculley et al., NeurIPS 2015](https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html)),
and systematic miscalibration, where stated confidence and observed
correctness diverge unless explicitly measured and corrected
([Guo et al., ICML 2017](https://proceedings.mlr.press/v70/guo17a.html)).

**Case: Aviation's Outcome Flywheel.** ASRS — the confidential,
non-punitive incident reporting system NASA has operated since 1976
([asrs.arc.nasa.gov](https://asrs.arc.nasa.gov/)) — plus the
mandatory-investigation regime for accidents, produced a feedback loop
that made commercial aviation's safety curve the reference artifact for
every other industry. **Outcomes were made cheap to report, safe to
admit, and mandatory to learn from.**

**Case: Zillow Offers (2021).** A pricing model's calibration broke
under a fast-moving market regime; the company compounded it with
deliberately aggressive bidding; and — the textbook feedback-loop clause —
the program's own purchases fed the comparable-sales environment it was
calibrating against. Write-downs in the hundreds of millions, roughly a
quarter of the workforce cut, the business line closed. **A learning loop
without independent ground truth is a confidence machine.**

**Translation.** Every episode closes with an outcome label — immediate
and delayed — produced from ground truth *independent of the agent's own
verdicts* (a system must never grade itself with its own answers).
Verdict-versus-outcome joins feed calibration measurement per confidence
band; misses feed new discriminating checks; policy thresholds move on
evidence, through controlled one-variable experiments with paired
statistics, never through vibes after a bad week.

> **The test:** *"When was this system last measurably wrong, and what
> changed because of it?"* A system that cannot answer has either never
> been wrong (false) or never looked (fatal).

---

### The Review Card

Nine questions, one per principle. Any new capability, tool, or autonomy
expansion answers all nine or explains why one does not apply — and the
exemption rate is itself tracked.

| # | Principle | The Question |
|---|---|---|
| 1 | Verdicts require epistemics | What would change the system's mind, and is that recorded? |
| 2 | Evidence requires provenance | Can a skeptic reproduce every material claim from its envelope? |
| 3 | State requires ownership | Who owns each persistent fact, and how are stale writes detected? |
| 4 | Autonomy requires a dial | What is this action's worst case, and who explicitly accepted it? |
| 5 | Inputs require a trust boundary | If every input were attacker-authored, what is the worst acted-on outcome? |
| 6 | Knowledge requires a clock | As of when is each fact true, and when does the conclusion expire? |
| 7 | Delegation requires ceilings | Can any child path exceed the root's authority — and the fleet's worst correlated hour? |
| 8 | Failure requires a ladder | What is the second-worst mode, and has it been rehearsed? |
| 9 | Learning requires outcomes | When was the system last measurably wrong, and what changed? |

The review card is executable: the
[trustworthy-autonomy rubric](../../rubrics/trustworthy-autonomy.md)
turns these nine questions into judge-scored criteria graded against
real agent sessions, and the
[rollout-reviewer-tenets rubric](../../rubrics/rollout-reviewer-tenets.md)
does the same for the session-observable tenets of Part III.

### Composition — The Principles as a Control Structure

Leveson's frame makes the architecture obvious: each principle is a
*constraint layer*, and trustworthiness is the property of the whole
control structure, not of any component — least of all the model.

```
  trusted inputs (P5)  →  time-correct knowledge (P6)
      →  epistemic verdicts (P1)  ←  provenanced evidence (P2)
      →  owned state (P3)
      →  dialed authority (P4), bounded delegation (P7)
      →  laddered failure (P8)
      →  labeled outcomes (P9)  →  ┐
                                   │  feeds back into P1's calibration
                                   └─ and P4's earned autonomy
```

Two composition rules matter more than any single principle:

**The weakest-layer rule.** The layers are conjunctive — each is
necessary for the layers downstream of it to mean anything. Perfect
provenance under an unbounded autonomy dial is a well-documented
catastrophe; a perfect dial acting on laundered evidence is a
confidently-authorized mistake. When any layer is weak, the system should
*downgrade adjacent layers* — lower autonomy when provenance is thin,
prefer abstention when inputs are suspect, shorten decision horizons when
state is contested.

**The earned-autonomy loop.** P9's outcome labels are what turn P4's dial
from a policy document into a *market*: autonomy is purchased with
calibration evidence, per action class, per service class — and is
repossessed on defined triggers (a metric regression past a pre-declared
floor, not a mood). This loop is the only legitimate mechanism for
autonomy expansion. Anything else — a demo went well, a customer asked,
a quarter ended — is Rasmussen's drift wearing a business case.

### What We Deliberately Did Not Make a Principle

Four candidates were argued and held out; recording why is part of being
arguable-with:

| Candidate | Why it is not a separate principle |
|---|---|
| **Tenancy and data boundaries** | Its failure mechanism is P2/P3 applied at an organizational boundary — not a new mechanism. Carried as a first-class gap (G9). |
| **Agent identity and action attribution** | P2's envelope discipline extended to actions. Belongs in the audit layer. |
| **Explainability as consumption** | The handover must be legible under stress, not merely justified. Owned by the decision-experience work (G6), not a tenth principle. |
| **Cost governance** | A rung of P4's dial and a term in P7's ceilings. Not a distinct failure mechanism. |

The admission criterion: a distinct failure *mechanism*, not a distinct
name. A future revision may promote any of these if operating evidence
shows the mechanism is distinct after all.

---

## Part III — The Rollout Reviewer: Principles Applied

### What the Reviewer Is

One session reviews **one checkpoint of one rollout episode**
(T+0/5/15/30 ladder). Here is the honest inventory of how the system
works:

| Component | What it does | Who owns it |
|---|---|---|
| **Relay** | Fires the checkpoint ladder; owns the clock | Platform (Ensemble) |
| **rollout-intel** | Append-only episode/checkpoint store + bitemporal dossier journal | Platform (Ensemble) |
| **gcp-observe** | Collects and HMAC-signs observation bundles | MCP server (platform-operated) |
| **Policy pack** | Deterministic rules evaluated server-side by the recorder | Platform (Ensemble) |
| **Recorder** | Re-runs policy at record time; rejects contradicting verdicts | Platform (Ensemble) |
| **The agent** | Interprets evidence, produces verdicts + reports | Rollout Reviewer (model + skill) |
| **Outcome collector** | Labels episodes from ground truth at 30m/2h/24h | Platform (Ensemble) |
| **Eval suite** | Golden runs via deterministic twin; paired-statistics experiments | Platform (Ensemble) |

Evidence arrives as a server-collected, HMAC-signed observation bundle
scoped to the service under review. The agent's verdict — exactly one of
`healthy | regression-suspected | insufficient-evidence` — is recorded
via `record_checkpoint`, where the recorder re-runs policy and rejects
contradictions.

Skills ship as a versioned progressive-disclosure package (contract body
+ on-demand playbooks for noise isolation, scope triage, evidence
gathering, and stability checks). Memory is a governed dossier store the
agent can read and *propose* to, never write; precedents arrive balanced
(up to 2 healthy + 2 unhealthy labeled episodes, architecture-compatible).

That is the machine the tenets below govern. Where a tenet describes
something not yet true in production, the [gap register](#the-gap-register)
says so.

---

### Ten Operating Tenets

Each tenet names the principle(s) it implements, the mechanism that
enforces it, and its violation smell — the PR or design pattern that
should trigger a review.

---

#### T1 — The policy is the floor; judgment only tightens.

*Principles 1, 4*

The deterministic policy pack is evaluated server-side, and the recorder
rejects any verdict that contradicts it. Interpretation may harden a
policy pass into `regression-suspected` — with evidence — but may never
soften a policy fail into `healthy`. This asymmetry makes the model's
eloquence *structurally irrelevant* to the safety floor.

**The priced cost:** tighten-only means the system will sometimes record
a verdict its own reasoning believes is wrong (a policy fail the evidence
says is scanner noise still records as regression-suspected). That is a
deliberate trade — floor integrity over per-verdict precision — and it
has a dethroning statistic: if the false-pause cost curve ever exceeds
the expected floor-breach cost, this tenet gets re-argued with numbers.

It also has an attack surface: adversarial tightening as deployment
denial-of-service (see P5). The response is detection, not loosening.

> **Violation smell:** any PR, prompt, or playbook that gives the agent a
> path to argue a failing rule down.

---

#### T2 — Unsigned evidence is hearsay.

*Principles 2, 5*

Every observation is minted and HMAC-signed at the MCP server, and
rollout-intel verifies both signature and *scope*: evidence about a
different service cannot satisfy this episode's policy. The key is
symmetric, shared between exactly two server processes, and ships with a
dev-default that production MUST override.

> **Violation smell:** a tool or "quick integration" that lets
> unauthenticated numbers reach the verdict path.

---

#### T3 — `insufficient-evidence` is a first-class success.

*Principle 1*

Thin traffic, missing observations, and unverifiable envelopes yield an
honest "no call." The policy pack's min-samples rule enforces it
deterministically: below the sample floor, the outcome is
insufficient-evidence, *never* healthy. A reviewer that always has an
answer is a reviewer that is sometimes lying.

> **Violation smell:** treating abstention as a failed eval. Rubrics must
> score justified abstention as correct behavior.

---

#### T4 — The episode is the truth; the report is its shadow.

*Principle 3*

Durable state lives in rollout-intel: an append-only episode/checkpoint
store beside the bitemporal dossier journal (valid time + record time;
`as_of` reads that never resurrect expired claims).
`/workspace/rollout-report.md` is a projection for humans — a map, not
the territory. The agent never self-schedules, never keeps private state
files, never treats its own prose as memory.

> **Violation smell:** any design where the report is the only place a
> fact lives.

---

#### T5 — Memory advises; it never testifies.

*Principles 2, 3, 6*

Dossiers are read-only projections of a governed journal: agents
*propose* (as hypothesized/asserted claims), humans promote; only
approved/observed claims are governed truth. Precedents are balanced on
purpose, labeled-only, time-correct, and **never satisfy a policy rule**
— structural by construction, since policy evaluation consumes only
observation envelopes and precedent data has no input path.

> **Violation smell:** prior episodes substituting for live evidence;
> unbalanced precedent retrieval.

---

#### T6 — Autonomy is a spec field, not a personality trait.

*Principles 4, 7*

The human-in-the-loop dial is a one-section spec diff
(`unlistedMcpTools: allow` vs `ask`) — same agent, same skill, two
authority postures. The pattern is demonstrated live by incident-manager
(base vs hitl variants). Read-only is structural: no mutating verbs, no
shell tool, no network egress, credentials with servers only. Capability
bindings add the graduated layer: ceilings, scope narrowing, trust
floors.

> **Violation smell:** autonomy posture written into prompts or
> playbooks; "don't ask permission" in any skill text.

---

#### T7 — Every change is an experiment, or it is a regression risk.

*Principle 9*

Specs are immutably versioned; the one-change rule rejects experiments
that vary more than one spec section; paired runs produce bootstrap
confidence intervals, a sign test, and a cost guard. The deterministic
scripted twin (fake model, identical spec otherwise) keeps golden runs
meaningful. Skills bump semver on every content change — same-version
republish is refused loudly.

> **Violation smell:** "small prompt tweak" merged without a version bump
> or an experiment.

---

#### T8 — Outcomes grade us; demos do not.

*Principle 9*

Ground-truth labels come from the world, never from the agent's own
verdicts. Labels are write-once. Machine promotion *suggestions* require
recurrence (≥3 labeled supporting episodes, no contradiction) and gate
the suggestion surface — the human remains the promotion authority. The
metric that matters: verdict-versus-outcome (regression recall, healthy
precision, justified-abstention rate) segmented by stage.

> **Violation smell:** celebrating rubric scores as quality; training on
> labels the reviewer itself produced.

---

#### T9 — The model is a replaceable part.

*Principles 3, 4*

Everything that makes the reviewer trustworthy — signed evidence,
deterministic policy, episode state, verdict contract, eval machinery —
lives outside the model. A model swap is a one-section spec change,
experiment-comparable like any other. Structurally, P3/P4 demand trust
live outside the component being trusted; commercially, the platform
thesis demands the moat survive model churn. If those two arguments ever
diverge, the structural one wins.

> **Violation smell:** verdict semantics or safety behavior that depends
> on a specific model's disposition.

---

#### T10 — Noise is a hypothesis, not an excuse.

*Principles 1, 6*

Scanner probes spike during rollouts because IP and load-balancer
reassignment exposes new endpoints; stdlib 4xx logging masquerades as
server errors — but every noise claim must survive the
baseline-consistency test and be quantified (partition by status class
and path shape; compare partitions across non-overlapping windows). And
per T1: suspected noise under a policy fail changes the reasoning
summary, never the verdict.

> **Violation smell:** "probably scanners" without partition numbers;
> overlapping baseline/treatment windows.

---

### The Contribution Contract

How to evolve the reviewer without eroding it. Each rule cites the tenet
it protects.

| # | Rule | Protects |
|---|---|---|
| 1 | **Rubric-first for new behavior.** A capability that cannot be observed by a rubric criterion is a capability that cannot regress detectably. Land the check with the change. | T8 |
| 2 | **One change per experiment; experiment per change.** Skill content bumps semver; spec changes touch one section; candidate vs base runs on pinned golden datasets. | T7 |
| 3 | **Playbooks over prompt growth.** New judgment ships as a `references/` playbook with an "applies when" header. The contract body stays under ~100 lines. | T4, T9 |
| 4 | **Verdict vocabulary is frozen until the recorder moves.** No skill introduces new verdict words. A vocabulary change is a platform change. | T1, T3 |
| 5 | **New tools enter through capability review.** Any new evidence source declares tool→scope claims, gets projected under the capability ceiling, and starts ask-gated. | T2, T6 |
| 6 | **Autonomy expansions cite outcome data.** Moving any action class up the dial requires calibration and precision/recall record. A demo is not a citation. | T6, T8 |
| 7 | **Honest failure modes in every skill.** Every playbook states what to do when evidence is unavailable — and the answer is always a variant of "declare the gap, widen uncertainty, prefer abstention." | T3 |

---

### Autonomy Expansion Gates

The reviewer sits at observe/analyze/recommend (levels 0–2) today, with
recording as its only "action" — and that action is policy-checked at the
recorder. Movement up the dial follows staged gates with numeric floors:

| Gate | Authority Added | Evidence Floor | Sign-off | Auto-Revoke When |
|---|---|---|---|---|
| **A — Notify** | Notify service owners for defined severity classes | ≥50 labeled episodes; notification precision ≥0.8 on replay; projected page rate within team's pre-declared budget | Owning team lead | 30-day precision < 0.7, or page budget exceeded 2× in a quarter |
| **B — Tune** | Shorten/extend checkpoint ladder within configured bounds | Replay evidence of detection-latency gain at equal FP rate; starts on ≤10% of episodes with paired comparison | Platform owner | FP-rate degradation at 95% CI, or any regression attributable to a shortened ladder |
| **C — Hold** | Hold a canary-scale stage (prepare + policy-bounded execute) | Stage-level precision & recall over ≥100 labeled episodes; reversal rehearsed in golden suite; blast-radius ceiling in the tool | Service owner + platform owner | Any hold later labeled unnecessary 2× in 90 days, or one reversal-path failure |
| **D — Broad** | Anything touching broad production | Multi-quarter labeled history, fail-closed policy engine, organizational decision | Named human role per customer policy | Not applicable — does not auto-grant |

The gates encode the composition rule from Part II: autonomy is
*purchased* with outcome evidence and *repossessed* on pre-declared
triggers. There is no other currency.

---

## Part IV — Value and Competitive Position

### The Buyer's Question

Nobody buys a rollout reviewer because their engineers cannot write a
prompt. The question a platform lead is really answering:

> "Do we want to **build, evaluate, secure, operate, audit, and
> continuously improve** a production decision system that may influence
> high-impact releases — and carry its 2 a.m. pager?"

That sentence contains six verbs; a prompt arguably covers half of one
of them. The product is everything else: the control structure from
Part II, operated as a service, with the calibration receipts.

### The Commodity Baseline

Be maximally honest about what is already abundant, because a moat built
on any of it is rented:

| Commodity | Why it is table stakes |
|---|---|
| Frontier-model access and agent harnesses | Coding/workspace agents with skills, runs, and delegation are platform features now |
| Tool connectivity | MCP made connectors a spec sheet, not an advantage |
| Trace-derived service graphs | OpenTelemetry-class infrastructure is standardizing topology |
| Progressive-delivery gates | Argo Rollouts / LaunchDarkly-class systems already do metric analysis and automated rollback |
| Fluent reports | Narrative generation is free; unbacked narrative is worth what it costs |

A "reviewer" that is a prompt over dashboards sits entirely inside this
commodity set. **The moat must live in the layers a prompt cannot carry —
evidence, state, policy, outcomes, and workflow.**

### Two Products, One Control Structure

The offer is genuinely two-layered, and the layers reinforce:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENSEMBLE (the platform)                       │
│                                                                 │
│  Governed agent operations — horizontal primitives:              │
│  • Immutable versioned registries (specs, skills, rubrics)      │
│  • One-change experiments with paired statistics                │
│  • Capability bindings with ceilings, projection, trust floors  │
│  • Structural sandbox (no shell, no egress, credentials w/      │
│    servers)                                                     │
│  • Deterministic twin pattern (FakeProvider)                    │
│  • Session budgets + delegation ceilings                        │
│  • Audit throughout                                             │
│                                                                 │
│  In principle terms: P3, P4, P5, P7 as infrastructure           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              ROLLOUT REVIEWER (the product)                 │ │
│  │                                                             │ │
│  │  Decision-grade rollout intelligence — vertical machinery:  │ │
│  │  • Append-only episodes + checkpoint ladders                │ │
│  │  • HMAC-signed, scope-verified observation envelopes        │ │
│  │  • Deterministic policy with recorder rejection             │ │
│  │  • Governed service dossiers (bitemporal, propose/promote)  │ │
│  │  • Balanced labeled precedents, time-correct retrieval      │ │
│  │  • Ground-truth outcome labeling at multiple horizons       │ │
│  │  • Three-verdict epistemic contract                         │ │
│  │                                                             │ │
│  │  In principle terms: P1, P2, P6, P9 as domain machinery    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

The platform without the vertical is a very good harness. The vertical
without the platform is a bespoke system someone must now operate. The
buyer's alternative is building **both**.

### The Moat Stack

Five systems "customers should not have to build themselves," mapped to
what exists — with maturity grades a skeptic can audit:

| # | Layer | Our Mechanism | Maturity | Compounding Asset |
|---|---|---|---|---|
| 1 | **Context graph & compiler** | Service catalog + context pack identity; dossiers as service priors; **no topology/dependency graph yet** | Partial → Roadmap | Time-aware service knowledge — the thinnest layer today |
| 2 | **Epistemic decision & evidence ledger** | Signed + scope-verified envelopes; three-verdict contract with enforced abstention; tighten-only interpretation; playbook'd noise discipline; **claim-graph granularity not yet** (G1/G2) | Partial | Provenance corpus + verdict record — raw material of calibration |
| 3 | **Episode & authority control plane** | Append-only episodes + bitemporal dossier journal; recorder-enforced verdict floor; dossier governance (propose/promote); spec-level autonomy dial; capability ceilings & trust floors; delegation clamps | **Proven in sim** | Workflow + policy history — the layer hardest to retrofit |
| 4 | **Outcome & evaluation flywheel** | Ground-truth labels at 30m/2h/24h, never from agent verdicts; write-once labels; one-change experiments with paired stats; deterministic twin | Proven in sim → **production closure is the work** (G4) | Labeled episodes + calibration data — the only asset that *compounds* |
| 5 | **Workflow embedding & decision experience** | Report projection with per-rule outcomes, causal chain, draft remediation; eval suites per agent; **decision-packet UX not yet** (G6) | Partial | Adoption at real decision points |

**Read the table cynically:** layers 3 and 4 are the differentiated core
today; layer 1 is the roadmap bet; layers 2 and 5 are connective tissue.
That is defensible precisely because 3 and 4 have the longest retrofit
time — durable authority semantics and outcome discipline are
organizational muscles, not features.

#### The Defensibility Equation

The source standard's moat equation (*moat = context × semantics ×
temporal correctness × decision integration × outcome learning × workflow
embedding*) is good rhetoric and bad math. Two true claims extracted and
stated precisely:

**True claim one — the factor set is tier-dependent.** The advisory
**Reviewer** tier does not need a topology graph to be valuable. Signed
evidence, the policy floor, honest abstention, and episode history
already beat a dashboard-reading prompt. **Guardian** adds action, so it
*does* require the fuller factor set. Each tier ships only when its
factors are nonzero.

**True claim two — the layers are conjunctive within a tier.** A strong
layer cannot compensate for a missing one. Provenance under an unbounded
dial is a catastrophe with receipts.

**The decision rule:**

> Marginal investment goes to the layer with the highest expected erosion:
> a function of (a) how weak it is for the *next* tier, (b) how fast a
> competitor reaches parity on it, and (c) how long its compounding asset
> takes to accumulate — **long-latency assets start earliest regardless
> of current strength, because you cannot buy back time.**

Under that rule: labeled episodes start compounding now. What competitors
genuinely cannot backfill is **decision-time capture**: which evidence
was available at the moment of each verdict. Retrospective replay can
approximate outcome labels; it cannot reconstruct decision-time evidence
availability — and that differential is exactly what calibration is made
of.

And one moat statement bears repeating: the tighten-only recorder, signed
evidence, and structural read-only posture make the reviewer's **safety
floor model-invariant**. "Make the model replaceable" prevents the moat
from being repriced every time a lab ships a better model.

### The Outcome Flywheel

The data-network-effect literature is clear that accumulated data
compounds only when the product *learns from it and returns the
improvement to users*. The loop, mechanism by mechanism:

```
     ┌──────────────────────────────────────────────────────────┐
     │                                                          │
     ▼                                                          │
  ① Every review → episode                                      │
     (checkpoints, evidence, verdicts, reasoning)               │
     │                                                          │
     ▼                                                          │
  ② Episode closes → ground-truth labels                        │
     (30m / 2h / 24h — independent of agent verdicts)           │
     │                                                          │
     ▼                                                          │
  ③ Labels + verdicts → per-service scorecards                  │
     (regression recall, healthy precision,                     │
      justified-abstention rate)                                │
     │                                                          │
     ▼                                                          │
  ④ Misses → discriminating checks                              │
     shipped via one-change experiments with paired stats        │
     │                                                          │
     ▼                                                          │
  ⑤ Proven improvements → return to tenant                      │
     (versioned skills + policy; per-tenant learning default;   │
      cross-tenant only as consented, aggregated patterns)      │
     │                                                          │
     ▼                                                          │
  ⑥ Expanded autonomy → more episodes at higher stakes ─────────┘
```

**The honesty condition:** the loop runs end-to-end in the simulator
today. Making episode closure a production contract (gap G4) is the
single highest-leverage investment in this document. Without step ② in
production, steps ③–⑥ are aspiration.

### Value by Persona

| Persona | What they get |
|---|---|
| **Service owner** | A reviewer that never mutates, never bluffs (abstention is honest), shows its evidence, and pages with receipts. Review minutes disappear; audit trail appears. |
| **SRE / release engineering** | Deterministic policy floors that models cannot argue down; staged checkpoints with per-stage evidence; false-page rates that are measured and contracted. |
| **Platform / AI enablement** | One governed way to run *any* agent — versioned, evaluated, capability-bounded, auditable — instead of a zoo of prompts with credentials. |
| **Compliance / risk** | Provenance envelopes, immutable versions, approval boundaries, and an audit answer to "why did the system say healthy?" Aligns with [NIST AI Risk Management Framework](https://www.nist.gov/artificial-intelligence/ai-risk-management-framework) expectations and EU AI Act documentation/monitoring obligations. |

### Prove It: The Three-Arm Baseline

The moat must be demonstrated, not asserted. One baseline is not enough —
a single comparison always holds the wrong thing constant. Three arms,
each answering a different skeptic, replayed over the same historical
episodes and scored by the paired-statistics engine:

| Arm | What it tests | The skeptic it answers |
|---|---|---|
| **Arm 0 — Policy pack alone** | No agent: deterministic policy over the standard evidence bundle, verdicts mapped mechanically | *"What is the measured marginal value of the model over the deterministic floor?"* — the sharpest question a buyer will ask |
| **Arm 1 — DIY on raw tools** | A capable generic agent, same MCP tools, rollout-review instructions, *no* trust machinery | *"Why can't I just build this myself?"* — scored on decision quality AND provenance + reliability |
| **Arm 2 — Vanilla on Ensemble** | Same platform, skill refs pointing at a plain prompt | *"Is the curated skill content worth paying for?"* — isolates the one-change skill delta |

Metrics across arms: regression recall, healthy precision, false-pause
rate, justified abstention, lead time, provenance completeness,
operational reliability, and — once G2/G4 land — calibration error.

Run it quarterly. Share the arm results with design partners, not just
internally — a moat measured only against one's own chassis, privately, is
still a story. **The moat is whatever remains measurably better after
every arm gets fair access.**

### Erosion Risks, Owned

| Risk | Reality | Our countermeasure |
|---|---|---|
| Topology/connector commoditization | Already happening (OTel, MCP) | Compete on time-correctness + provenance + decision integration, never on access |
| Vendor-native catch-up (progressive-delivery tools adding LLM judges) | Credible near-term | Own the cross-system decision layer and the epistemic contract they won't retrofit |
| Customer platform teams DIY | Rational for small homogeneous stacks — concede honestly | Win where context reconstruction is expensive; sell time-to-first-trustworthy-decision |
| Model-lab agents absorbing the harness layer | Partial — harnesses commoditize | Model-invariant safety floor + accumulated labeled episodes are the layers a lab cannot ship |
| No production outcome labels (self-inflicted) | The single most dangerous risk | G4 is the contract: no closure, no learning claim |
| Confidence theater creep | Cultural, constant | T3/T8 discipline; never ship numeric confidence before its calibration loop |

---

## Part V — The Road Ahead

### The Gap Register

Where the implementation has not caught up to the standard. Each gap is a
commitment the rest of the document leans on — if a quarter passes
without movement, the honest move is to weaken the dependent claims.

| # | Gap | Principles | Today | Direction |
|---|---|---|---|---|
| **G1** | Structured assessment record | P1, P2 | Reasoning in `record_checkpoint` summary + report; evidence linkage via signed bundle, not per-claim references | Extend checkpoint schema toward claim-level structure; rubric v3 rewards causal-chain completeness |
| **G2** | Calibrated confidence | P1, P9 | Three-verdict vocabulary carries the epistemic load | Add confidence only *with* its calibration loop (G4) — never before |
| **G3** | Context compiler / temporal topology | P3, P6 | Identity via catalog + context pack; dossiers carry service priors; no dependency graph | Config-describe read tools; AppTopology-class MCP surface; episode-linked topology snapshots |
| **G4** | Production outcome flywheel | P9 | Proven in sim (outcome collector, labeled corpus, learning gates) | Make episode closure + delayed labels a production contract; publish verdict-vs-outcome scorecards per service class |
| **G5** | Seasonality-aware baselines | P6 | Non-overlapping window discipline only | Policy pack v-next: matched-window comparisons where history allows |
| **G6** | Decision-packet UX | P1, P4 | Report includes verdict, per-rule outcomes, causal chain, draft remediation | Derive packet from checkpoint records — projection, not new state (T4) |
| **G7** | Multi-target release awareness | P3, P6 | Prose-level discipline in scope-triage playbook only | rollout-intel episode metadata for release linkage |
| **G8** | Rehearsed failure ladder | P8 | Fail-closed properties are structural; degraded modes not yet exercised as golden scenarios | Add degraded-mode cases to golden suite |
| **G9** | Tenancy and learning boundaries | P2, P3 | Tenant scoping on raw data; derived-learning path ungoverned | Per-tenant learning by default; cross-tenant only as consented, aggregated patterns |

### The Next Four Quarters

The sequencing rule, stated before the sequence so it can be checked
against it:

> **(1)** Credibility risk to claims already being made is retired first.
> **(2)** Long-latency compounding assets start as early as possible —
> label history cannot be bought later. **(3)** Bets on new surfaces come
> last, narrowest slice first. **(4)** Authority expands only behind its
> evidence.

| Quarter | Theme | Key Deliverables | Sequencing Rule |
|---|---|---|---|
| **Q1** | Retire credibility risk | Claim-level assessment structure (G1); degraded-mode golden scenarios (G8); decision-packet projection (G6) | Rule 1 — §7's audit story already leans on G1 |
| **Q2** | Start the compounding clock | Episode closure + delayed-outcome labels as production contract (G4); first verdict-vs-outcome scorecards; three-arm baseline run and shared | Rule 2 — everything that "cannot be bought later" |
| **Q3** | New surfaces, narrowest slice | Config-read surface for config-intent validation; release-linkage metadata (G7); topology facts with validity intervals; seasonality-matched baselines (G5) | Rule 3 — depth over breadth; time-correct semantics, not edge count |
| **Q4** | Authority behind evidence | Gate A (notify) and Gate B (ladder tuning) on flywheel evidence; Gate C attempted only where precision/recall floor is met; Guardian piloted; numeric confidence (G2) ships *with* its calibration measurement | Rule 4 — autonomy expands as far as scorecards justify |

---

## Appendix A — Objections, Honestly Handled

**"This is heavyweight. We need to ship."**

An observe-and-recommend agent needs P1 and P2 hygiene *and* P5's
structural protections — because a read-only reviewer holds the full
trifecta from session one, and a steered report that a human obeys is an
attack completed. What it can defer is the expensive upper machinery:
P4's execution rungs, P7's fleet controls, P9's full flywheel. P5's
protections are structural (sandboxing, signed channels, credential
custody) and amortize across every agent on the platform. Knight
Capital's 45 minutes erased years of velocity; the principles are how
you never have that day.

**"Models are getting smarter; most of this dissolves."**

Some genuinely might: better instruction-hierarchy training may shrink
injection susceptibility; better reasoning may improve hypothesis
quality. The part that cannot dissolve: **a system's self-reported
trustworthiness is testimony, and testimony requires independent
verification.** A model's claim to be calibrated is checked by an
outcome record it does not control. Verification independent of the
thing verified is not a limitation that intelligence outgrows — it is
what "trust" means.

**"Humans don't meet this bar either."**

Correct — individual humans don't. Institutions do, and that is the
point: chain of custody, peer review, double-entry books, flight rules,
two-person integrity are the *institutional technologies* humanity built
because individual judgment does not scale trust. Agents do not get to
skip the institutional layer; they get to inherit it on day one.

**"This is just process — and process gets ritualized."**

At scale, process *is* the product; nobody buys SRE because reliability
is exciting. The sharp version deserves respect: review cards *do* decay
into checkbox theater. So the apparatus must monitor itself: track the
exemption rate on the review card, audit a sample of exemptions each
quarter, and treat a rising rubber-stamp rate as a P9 signal about the
process.

---

## Appendix B — References and Further Reading

### Foundational Literature

| Work | Relevance | Link |
|---|---|---|
| Gettier, E. (1963). "Is Justified True Belief Knowledge?" *Analysis* 23(6) | Knowledge can be accidentally correct — the philosophical basis of outcome labeling | [DOI: 10.2307/3326922](https://doi.org/10.2307/3326922) |
| Conant, R.C. & Ashby, W.R. (1970). "Every good regulator of a system must be a model of that system." *Int. J. Systems Sci.* 1(2) | Agents need world models, not just reaction patterns | [DOI: 10.1080/00207727008920220](https://doi.org/10.1080/00207727008920220) |
| Perrow, C. (1984). *Normal Accidents: Living with High-Risk Technologies.* Basic Books | Interactive complexity + tight coupling = normal accidents | [Princeton UP](https://press.princeton.edu/books/paperback/9780691004129/normal-accidents) |
| Rasmussen, J. (1997). "Risk management in a dynamic society." *Safety Science* 27(2-3) | Systems drift toward the boundary under efficiency pressure | [DOI: 10.1016/S0925-7535(97)00052-0](https://doi.org/10.1016/S0925-7535(97)00052-0) |
| Parasuraman, R., Sheridan, T.B. & Wickens, C.D. (2000). "A model for types and levels of human interaction with automation." *IEEE Trans. SMC* 30(3) | Automation as degrees, not binary — the basis of the autonomy dial | [DOI: 10.1109/3468.844354](https://doi.org/10.1109/3468.844354) |
| Leveson, N. (2011). *Engineering a Safer World.* MIT Press | Accidents are control-structure failures, not component failures | [MIT Press (open access)](https://direct.mit.edu/books/book/2908/Engineering-a-Safer-World) |
| Hollnagel, E. (2014). *Safety-I and Safety-II.* Ashgate/Routledge | Design the adaptations, not just the protections | [Routledge](https://www.routledge.com/Safety-I-and-Safety-II-The-Past-and-Future-of-Safety-Management/Hollnagel/p/book/9781472423085) |
| Weick, K.E. & Sutcliffe, K.M. (2015). *Managing the Unexpected.* 3rd ed. Jossey-Bass/Wiley | High-reliability organization practices — agent-spec-shaped | [Wiley](https://www.wiley.com/en-us/Managing+the+Unexpected%3A+Sustained+Performance+in+a+Complex+World%2C+3rd+Edition-p-9781118862414) |

### Machine Learning and Calibration

| Work | Relevance | Link |
|---|---|---|
| Sculley, D. et al. (2015). "Hidden Technical Debt in Machine Learning Systems." *NeurIPS* | Hidden feedback loops, the technical-debt taxonomy for ML systems | [NeurIPS](https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html) |
| Guo, C. et al. (2017). "On Calibration of Modern Neural Networks." *ICML* | Modern networks are systematically miscalibrated — why confidence needs measurement | [PMLR](https://proceedings.mlr.press/v70/guo17a.html) |

### Standards and Frameworks

| Standard | Relevance | Link |
|---|---|---|
| SAE J3016 (2021). Taxonomy and Definitions for Terms Related to Driving Automation Systems | The graduated-autonomy framework that informed the autonomy dial | [SAE International](https://www.sae.org/standards/content/j3016_202104/) |
| W3C PROV (2013). The PROV Family of Documents | Data model for provenance — entities, activities, agents, derivations | [W3C](https://www.w3.org/TR/prov-overview/) |
| NIST AI Risk Management Framework (2023) | Documentation, monitoring, and oversight expectations for AI systems | [NIST](https://www.nist.gov/artificial-intelligence/ai-risk-management-framework) |

### Incident Reports and Postmortems

| Incident | Year | Key lesson | Source |
|---|---|---|---|
| Three Mile Island | 1979 | Commanded ≠ actual — the epistemic collapse | [NRC NUREG-0585](https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr0585/) |
| Morris Worm | 1988 | Aggregate delegation without enforced ceilings | [Spafford, Purdue CSD-TR-823](https://docs.lib.purdue.edu/cstech/714/) |
| Air France 447 | 2009 | Uncertainty must be handed over explicitly | [BEA Final Report](https://www.bea.aero/en/investigation-reports/notified-events/detail/event/accident-to-the-airbus-a330-203-registered-f-gzcp-operated-by-air-france-on-1st-june-2009-in-t/) |
| Knight Capital | 2012 | State without ownership — $440M in 45 minutes | [SEC File 3-15570](https://www.sec.gov/litigation/admin/2013/34-70694.pdf) |
| GitLab database | 2017 | Untested backups are rumors about safety | [GitLab Postmortem](https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/) |
| AWS S3 | 2017 | Even human authority needs blast-radius limits | [AWS Summary](https://aws.amazon.com/message/41926/) |
| Boeing MCAS | 2018–19 | High authority, single sensor, no dial | [FAA JATR Report](https://www.faa.gov/news/media/attachments/Final_JATR_Submittal_to_FAA_Oct_2019.pdf) |
| Cloudflare | 2019 | The fast path is part of the system | [Cloudflare Blog](https://blog.cloudflare.com/cloudflare-outage/) |
| SolarWinds | 2020 | Trusted channel, untrusted content | [CISA Advisory](https://www.cisa.gov/news-events/news/joint-statement-federal-bureau-investigation-fbi-cybersecurity-and-infrastructure-security) |
| British Post Office Horizon | 1999–2024 | Numbers without lineage imprisoned people | [Post Office Inquiry](https://www.postofficeinquiry.org.uk/) |
| Meta outage | 2021 | Recovery paths must survive the failure they fix | [Meta Engineering](https://engineering.fb.com/2021/10/05/networking-traffic/outage-details/) |
| Zillow Offers | 2021 | Learning loop without independent ground truth | SEC filings and press coverage |
| XZ Utils backdoor | 2024 | Supply chain: trust the artifact, not the pipe | [oss-security disclosure](https://www.openwall.com/lists/oss-security/2024/03/29/4) |
| CrowdStrike | 2024 | Content updates need staged rollout too | [CrowdStrike PIR](https://www.crowdstrike.com/blog/falcon-content-update-preliminary-post-incident-report/) |

### Institutional Learning

| System | Relevance | Link |
|---|---|---|
| NASA ASRS (Aviation Safety Reporting System) | The outcome flywheel that made commercial aviation's safety curve the reference | [asrs.arc.nasa.gov](https://asrs.arc.nasa.gov/) |

---

> *The adversarial review record for the source material behind this
> document is in
> [04-independent-critique.md](../principles/04-independent-critique.md)
> — three independent critics, 50+ findings, every one dispositioned.*

---

*Last updated: July 2025. This is a living document. The gap register and
roadmap are load-bearing commitments — if they stop moving, the claims
they support should be weakened, not left to ride.*
