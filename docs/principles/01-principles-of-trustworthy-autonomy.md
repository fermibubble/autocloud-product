# The Principles of Trustworthy Autonomy

**The philosophical foundation for building agents that deserve production.**

*Companion to the Rollout Reviewer Team Standard v2.0 ("Trustworthy Autonomy
and Defensible Product Advantage for Rollout Reviewers"). That document
states four principles as engineering contracts. This one asks why those
four are the right ones, what intellectual tradition they descend from,
where they have already been paid for in blood and money, and what
additional principles operating agents forces into existence. It is
written to be argued with — and it has been: every factual claim below
survived an independent fact-check, and the argument structure survived an
adversarial review recorded in
[04-independent-critique.md](04-independent-critique.md).*

---

## 0. The central claim

An autonomous agent is a system that **converts uncertain evidence into
consequential action under delegated authority**. Every word of that
sentence is load-bearing:

- *Uncertain evidence* — the agent never has the world, only measurements
  of it, taken at some time, through some instrument, with some coverage.
- *Consequential action* — its outputs change things: deployments pause,
  people get paged, money moves, conclusions enter records that outlive
  the conversation.
- *Delegated authority* — someone lent it power, and that someone remains
  accountable. Delegation without a contract is abdication.

Capability answers "can it do the job?" Trustworthiness answers a
different question: **"what happens when it is wrong?"** — because it will
be wrong, and a system that is wrong *safely, legibly, and recoverably* is
categorically different from one that is wrong silently. The source
standard compresses this into a failure chain; extended to cover the full
principle set, it reads:

    poisoned or in-band input → stale knowledge → unsupported verdict
      → unverifiable evidence → unowned state
      → unbounded action, amplified by unbounded delegation
      → cliff-edge failure → unlabeled outcome
      → the same failure again, now with more confidence

Each principle below is a cut-point in that chain. None of this is novel;
that is precisely its strength. We are inheriting three centuries of
epistemology, eighty years of control theory, and fifty years of safety
science. The failure modes of autonomous agents are not new failure
modes — they are old ones wearing a new interface.

---

## 1. The intellectual inheritance

Three older disciplines already solved large parts of this problem. We
cite them not for decoration but because each supplies a working tool.

**Epistemology — the discipline of justified belief.** The traditional
analysis of knowledge as *justified true belief* — often traced to
Plato — was famously dismantled by Gettier's 1963 counterexamples, which
showed that justification, truth, and belief can all be present while
knowledge is absent: you can be right by accident. That is exactly the
production incident that outcome-labeling catches: the reviewer said
"healthy," the rollout was healthy, and the verdict was still *lucky*
because the discriminating evidence was never examined. Peirce's
*abduction* — hypothesis generation, roughly what later philosophy calls
inference to the best explanation — is the formal name for what a
diagnostician does; Popper's *falsification* teaches that a hypothesis
earns standing only by surviving attempts to kill it, which is why a
verdict must ship with its **discriminating checks**, the observations
most likely to overturn it. Bayesian updating supplies the arithmetic of
changing one's mind, and Hume's problem of induction is the polite
reminder that "it held for the last hour" never *entails* "it holds now" —
the floor under every **decision horizon** in this document.

**Cybernetics — the discipline of regulation.** Ashby's law of requisite
variety — in his own words, "only variety can destroy variety" — means a
controller must have at least as many distinguishable responses as the
disturbances it must counter. An agent with one response ("looks fine")
cannot regulate a production system with a thousand failure modes. Conant
and Ashby sharpened it in 1970 with the theorem that is also their
paper's title: **every good regulator of a system must be a model of that
system**. An agent without an explicit world model — topology, ownership,
change history — is not regulating; it is reacting.

**Safety science — the discipline of organized failure.** Perrow's
*Normal Accidents* (1984) argued that systems combining **interactive
complexity** with **tight coupling** produce accidents as a normal
property, not an anomaly — and an LLM agent wired into production tooling
is both interactively complex and tightly coupled by construction.
High-reliability-organization research (Weick & Sutcliffe) catalogs the
practices of organizations that defy Perrow's odds — carrier decks,
air-traffic control — and its five habits read like an agent spec:
preoccupation with failure, reluctance to simplify, sensitivity to
operations, commitment to resilience, deference to expertise. Rasmussen's
drift model warns that systems migrate toward the boundary of acceptable
performance under efficiency pressure — autonomy granted will be autonomy
leaned on. And Leveson's STAMP reframes the whole problem: **accidents are
not component failures; they are control-structure failures** — inadequate
constraints on a system whose components all "worked." That is the deepest
justification for this document: the model is a component; trustworthiness
is a property of the control structure around it.

One more inheritance deserves naming because it is five centuries old and
still in production: **double-entry bookkeeping** (codified by Pacioli,
1494, from older Venetian practice). Every entry has a counterpart; the
books must balance; fraud and error surface as violated invariants. It is
the oldest deployed system of machine-checkable provenance — and the
intuition behind evidence ledgers and idempotent report generation.

---

## 2. The principles

The first four are the source standard's, deepened. The following five
are what **operating** agents in an adversarial, temporal, consequential
environment forces into existence — only one of them (delegation) waits
for a platform of many agents; the rest bite the very first reviewer you
ship. Each principle gets the same treatment: the claim, the
philosophical root, real-world evidence, the translation to agent
systems, and the test a reviewer should apply.

---

### Principle 1 — Verdicts require epistemics

**A conclusion without its justification structure is not knowledge; it is
a guess with confidence-colored paint.**

*Root.* The observed/inferred distinction is the oldest tool in
epistemology, and the most commonly dropped in production. A verdict is a
compressed claim; epistemics is the decompression algorithm: what was
seen, what was concluded, how strongly, what is missing, what would change
the answer.

*Case.* Three Mile Island, March 1979. A pilot-operated relief valve stuck
open, draining coolant. The control-room indicator did not show the
valve's *position* — it showed that the close command had been *sent*. The
operators read an inference ("we commanded it closed") as an observation
("it is closed") and spent over two hours fighting the wrong failure. The
instrument did not lie; the interface collapsed the epistemic distinction
between commanded state and actual state. Most agent hallucination
incidents are exactly this shape: an inference presented in the
grammatical form of an observation.

*Case, second.* Air France 447, 2009. Iced-over pitot tubes fed the
autopilot inconsistent airspeed; the automation disengaged and handed a
suddenly-degraded information environment to a crew given no structured
account of *what the system no longer knew*. The full accident involved
more threads than this one — but the handover thread is the one that
generalizes: **uncertainty must be handed over explicitly**, because the
consumer of a verdict inherits its blind spots.

*Translation.* An agent's assessment is a structured object, not a
sentence: observations (with evidence references), inferences (marked as
such, with the observations they depend on), calibrated confidence,
enumerated unknowns, surviving alternative hypotheses, the discriminating
checks that would settle them, and a validity horizon. Abstention —
"insufficient evidence" — is a first-class verdict, and the selective
prediction literature treats it as exactly that: a managed risk-coverage
trade-off, not a failure. Confidence must be a measured quantity, not a
linguistic register; an uncalibrated "0.92" is what the source standard
rightly calls *confidence theater*.

*The test.* Ask of any verdict: **"What would change your mind?"** If the
system cannot answer, it does not hold a belief; it holds a slogan.

---

### Principle 2 — Evidence requires provenance

**A claim you cannot trace is a rumor, no matter how quantitative it
looks.**

*Root.* Courts developed chain of custody, science developed methods
sections and citation, accounting developed the audit trail — three
independent traditions converging on the same invariant: **the value of
evidence is inseparable from the record of where it came from and what
was done to it.** W3C PROV gives this a data model (entities, activities,
agents, derivations); content-addressed storage (the mechanism inside
git) gives it an immutability primitive.

*Case.* The British Post Office Horizon scandal — arguably the largest
provenance failure in legal history. Between 1999 and 2015, more than
nine hundred subpostmasters were prosecuted for theft and false
accounting based on shortfalls reported by the Horizon accounting system.
The evidence *looked* quantitative — ledgers, balances, precise sums — and
courts operated on a presumption that computer records were reliable. The
system in fact had known defects; remote-access modifications to branch
accounts were possible and initially denied. Convictions began to be
overturned in late 2020, the landmark Court of Appeal ruling followed in
2021, and the scale of the injustice ultimately required statutory mass
exoneration in 2024. Numbers without lineage did not merely mislead —
they imprisoned people. When an agent's report says "error rate rose to
2.4%," the difference between evidence and Horizon is: source system,
exact query, time window, retrieval timestamp, transformation history,
coverage, and an immutable reference.

*Translation.* Two mechanisms matter beyond the provenance envelope
itself. First, **epistemic laundering**: multi-step agent workflows
summarize summaries, and a hedged observation becomes a confident "fact"
three artifacts downstream unless claims carry their identifiers,
confidence, and caveats *through* every summarization. (Every child agent
that reports to a parent is a laundering opportunity.) Second,
**authenticated evidence**: in adversarial environments, provenance must
be cryptographic, not conventional — evidence signed at the source, scoped
to the subject under review, verified at use. A claim that arrives through
an unauthenticated channel from the system *being judged* is testimony
from an interested party.

*The test.* Pick any number in the report and ask: **"Show me the query,
the window, and the snapshot."** If reproducing the claim requires trusting
the agent's memory, there is no claim — only prose.

---

### Principle 3 — State requires ownership

**Persistent facts without an authoritative owner converge on fiction.**

*Root.* Distributed-systems theory has spent fifty years on exactly this:
Lamport taught us that "what happened when" is not free in a distributed
world; consensus protocols exist because *somebody must be authoritative*
about shared state; event sourcing and durable-execution engines exist
because reconstructing truth from an append-only history beats trusting a
mutable snapshot. The philosophical framing is Korzybski's: *the map is
not the territory* — and a report is a map.

*Case.* Knight Capital, August 1, 2012. A deployment reused an old feature
flag whose previous meaning — a defunct trading function unused since
about 2003, known internally as Power Peg — was still wired into dormant
code, and the rollout reached only seven of eight servers. The eighth
server interpreted the repurposed flag under its old semantics and fired
orders continuously: roughly $440 million lost in about 45 minutes (the
firm's reported pre-tax figure; the SEC's order puts it above $460
million), ending the company's independence. Every layer of the failure
is a state-ownership failure: a flag whose *meaning* had no owner or
lifecycle, a deployment whose *completeness* was not an owned,
reconciled fact — nothing asked "does reality match intent?" — and
semantics that had silently decayed for nine years (a staleness thread
Principle 6 will pick back up).

*Case, second.* GitLab, January 31, 2017. An engineer, fatigued and
fighting replication lag, ran a destructive removal on what he believed
was the failing secondary database — it was the primary. Five separate
backup mechanisms then turned out to be broken or misconfigured; roughly
six hours of production data were lost. The write-up is a classic honest
postmortem, and the structural lesson is that "which server am I on" and
"do the backups actually restore" were state nobody authoritatively owned —
they were assumptions.

*Translation.* Every persistent field in an agent system needs an owner,
a version, a lifecycle, and a conflict policy. The agent's report is a
**projection** of operational state, never the source of truth — the
moment the narrative document *is* the state machine, a wording change is
a state transition and a summarizer can silently roll back reality.
Concretely: the rollout controller owns rollout position; observability
owns telemetry; the reviewer owns assessments; the orchestrator owns
workflow progress; humans own approvals. Writes are versioned
(compare-and-swap, not last-writer-wins), terminal states actually
terminate, and memory that agents *propose* into is segregated from
memory that has been *promoted* by an authority.

*The test.* For any fact the system remembers, ask: **"Who is allowed to
change this, and how would we detect a stale write?"** If the answer is
"whoever wrote last," you have a rumor mill with persistence.

---

### Principle 4 — Autonomy requires a dial

**Authority must be action-specific, risk-priced, and revocable — an
all-or-nothing agent is a loaded institution-shaped object.**

*Root.* Human-automation research formalized this decades before LLMs:
Parasuraman, Sheridan, and Wickens (2000) modeled automation as *degrees*
across information acquisition, analysis, decision selection, and action
implementation — not a binary. Driving automation (SAE J3016's six
levels) made graduated autonomy a household concept. The dial is not
bureaucracy; it is the requisite-variety response to the fact that
different actions carry wildly different blast radii and reversibility.

*Case.* Boeing's MCAS. A flight-control function was granted large,
*repeating* authority over the horizontal stabilizer on the evidence of a
**single angle-of-attack sensor**, with no crew-facing disclosure of the
new authority and no intuitive dial to step it down. Two crashes — Lion
Air 610 (2018) and Ethiopian 302 (2019) — and a roughly twenty-month
grounding followed. Every ingredient of the anti-pattern is present:
high-authority action, low-quality evidence, no epistemic humility at the
sensor boundary, no graduated fallback, and an interaction model the
human operators had not been told about.

*Counter-case.* Apollo 11's landing computer, 1969. Minutes from the
surface, the guidance computer flooded with 1201/1202 executive alarms —
a radar-interface fault was stealing compute cycles. The system had been
*designed* with priority-based scheduling: it shed low-priority tasks and
kept flying the critical ones, and mission control, drilled on exactly
this failure signature, called "GO." That is the dial working: bounded
degradation instead of binary failure, plus humans who had rehearsed the
boundary.

*Case, third.* AWS S3, February 28, 2017. An authorized operator running
an established playbook mistyped one input and removed far more capacity
than intended, taking down S3 in us-east-1 for hours and much of the
internet with it. The fix was not "train harder" — it was to change the
tool so it could not remove capacity below a safety floor, or too much
too fast. **Even human authority needs the dial**; blast-radius limits
belong in the tool, not the intention.

*Translation.* Every tool call an agent can make gets an explicit
autonomy level — observe, analyze, recommend, prepare, execute-with-
approval, execute-within-policy — assigned by risk, reversibility,
confidence, environment, and blast radius, and *enforced structurally*
(the tool surface simply lacks the mutating verb; the credential lives
elsewhere; the permission is "ask") rather than rhetorically (a prompt
that says "please be careful"). The system fails closed on ambiguous
authority, and autonomy expansions are *earned* per action class from
measured outcomes, never granted globally. Corrigibility is part of the
contract: a human stop must always win, and the agent must not be able to
argue with the brake.

*The test.* For each action: **"What is the worst thing this can do at
this level, and who signed up for that?"** If the answer to the second
half is "nobody, implicitly," the dial is set wrong.

---

### Principle 5 — Inputs require a trust boundary

**The context window is a data channel. Command authority never arrives
in-band.**

*Root.* This is the oldest sin in computing wearing a new coat: in-band
signaling. Phone phreaking existed because the telephone network carried
control tones in the same channel as voice; SQL injection existed because
queries and data shared a string; and prompt injection exists because an
LLM's context window is one undifferentiated channel in which evidence,
instructions, and attacker text are typographically identical. The
confused-deputy problem completes the picture: an agent with legitimate
authority can be steered by an illegitimate principal if it cannot
distinguish who is asking.

*Evidence.* Honesty requires a disclosure the other principles don't
need: this principle's flagship evidence is **structural rather than
actuarial** — the argument is deductive, and we hold it anyway. Willison's
"lethal trifecta" formulation is the crispest: an agent combining
(a) access to private data, (b) exposure to untrusted content, and
(c) the ability to communicate externally is exploitable *by
construction* unless the trust boundary is engineered. (We extend the
third leg to any action channel, not just exfiltration.) A production
reviewer reads logs — attacker-writable by definition, since anyone who
can trigger an error writes to your logs — holds privileged evidence
access, and files reports humans act on: all three legs, every session.
The supply-chain record supplies the adjacent actuarial evidence: the XZ
Utils backdoor (2024) and SolarWinds (2020) were trusted *channels*
carrying untrusted content, trust assigned to the pipe rather than
verified on the artifact — precisely the mistake an agent makes when it
treats "output of my own tool" as "instruction from my principal."

*Translation.* One invariant is genuinely new here; two arrive from
neighboring principles and are named as such. New: **quoted content stays
quarantined** — log lines, metric labels, and tool payloads are displayed
as evidence, never obeyed as directives, however imperative their
grammar; the agent quotes suspicious content rather than complying with
it. From P2: evidence channels are authenticated and scoped — signed at
the source, verified at use, rejected when scope does not match the
subject under review. From P4: credentials live outside the blast
radius — the sandbox that processes untrusted content must not hold the
keys, so a fully steered agent still lacks the authority to act on its
confusion. And one attack the integrity framing misses: **availability**.
In a system where interpretation may only *tighten* (as it should — see
the tenets), an attacker who controls log content doesn't need to forge
health; injecting regression-shaped evidence, or starving the evidence
channel, weaponizes the system's own conservatism into a deployment
denial-of-service. The defense is the same discipline pointed the other
way: adversarial tightening is itself a detectable signature — repeated
tighten-pressure from low-provenance evidence pages a human instead of
silently pausing fleets.

*The test.* **"If an attacker authored every input this agent reads, what
is the worst outcome a consumer of its output would act on?"** Execution
is not the only harm; a steered report that a human obeys is the same
attack with a human in the loop as the final actuator.

---

### Principle 6 — Knowledge requires a clock

**Every fact the agent holds was true *as of some moment*, and decays;
reasoning that ignores time-correctness is reasoning about a world that
no longer exists.**

*Root.* Finance and law solved this with **bitemporality**: *valid time*
(when the fact was true in the world) versus *record time* (when the
system learned it). An assessment made at 14:32 about the window
14:00–14:30 using topology observed at 10:16 is a three-clock object, and
collapsing those clocks is how systems confidently describe yesterday.
Hume (§1) already set the philosophical floor: no regularity entails its
own continuation — so every conclusion carries a validity horizon.

*Why this is a separate principle.* Time-correctness could be distributed
as clauses of P1 (horizons), P2 (windows), and P3 (versioned state) — and
that is exactly how it gets lost: a cross-cutting concern distributed
across three owners has none. Staleness earns separate billing because it
is the failure mode that arrives *silently*: nothing errors when you
consult a current-state graph about a last-week checkpoint. It also
rarely gets the headline — it gets a contributing-factors paragraph in
everyone else's postmortem, which is why no single famous incident is
"the staleness incident."

*Evidence.* So this principle's case is a pattern, honestly marked as
such — and every operator has lived it: the dependency graph consulted
as-of-now to explain an incident that happened under last week's
topology; the 3 a.m. baseline compared against a 9 a.m. treatment window
and reported as a regression (a seasonality error, not a finding); the
runbook whose steps describe the architecture of two migrations ago;
feature flags and configuration changing behavior between binary
releases, so that "nothing was deployed" and "nothing changed" quietly
stop being synonyms. Knight Capital (P3) is also here: the flag's meaning
was true as of 2003, and for nine years no clock recorded its decay.

*Translation.* Topology, ownership, dependency, and exposure facts carry
validity intervals, observation timestamps, sources, confidence, and
coverage — a current-state answer is *wrong* for a historical question.
Baselines are windows with explicit boundaries, matched for seasonality
where history allows. The change taxonomy is complete on the time axis:
config, flags, schema, and data changes appear on the same clock as
binaries, because behavior does not care which pipeline changed it.
Memory follows the same law: what the system learned about a service last
quarter is a *prior*, timestamped and decaying, never a current
observation. And every verdict states how long it should be believed.

*The test.* For any fact in the context: **"As of when? Learned when?
Still valid on what assumption?"** Three timestamps or it is folklore.

---

### Principle 7 — Delegation requires ceilings

**A fleet of small, individually reasonable decisions is one large
decision wearing camouflage — authority must attenuate down the tree and
be priced in aggregate.**

*Root.* Goethe's sorcerer's apprentice is the founding myth: delegation
without bounded scope, plus no revocation protocol. Organizational theory
contributes subsidiarity and span-of-control; resilience engineering
contributes bulkheads. Half of this principle is honestly P4 applied
recursively — every delegatee gets a dial, set no looser than the
delegator's. The half that is *new* is the portfolio view: the question
is never only "is this action safe?" but **"are a thousand of these
actions, correlated, safe?"** — because errors delegated in parallel do
not diversify; they synchronize.

*Case.* The Morris worm, 1988. Its author *included* a limiting
mechanism — a probabilistic rule meant to prevent runaway reinfection —
and tuned it wrong; reproduction pressure alone overwhelmed a meaningful
fraction of the then-internet (the conventional estimate, rough by
nature, is on the order of a tenth of connected hosts). It remains the
cleanest demonstration that in self-amplifying systems, the *aggregate*
behavior is the system, and a mis-set ceiling is indistinguishable from
no ceiling at the fleet scale.

*Translation.* Child agents inherit *subsets*: tools no broader than the
parent's, network policy no looser, budgets as fractions that provably
sum below the parent's ceiling, depth and concurrency capped. Spawn
briefings are self-contained contracts (task, boundary, termination
condition, reporting format) because a child does not share the parent's
context — assuming it does is how instructions get laundered into
improvisation. Results are *collected*, never assumed: a child's silence
is a data point, not a completion. And aggregate exposure is a
first-class number with an owner and a ceiling of its own.

*The test.* **"Can any path through the delegation tree end with more
authority than the root was granted — and what is the fleet's worst
correlated hour?"** If either question has no owner, the ceilings are
decorative.

---

### Principle 8 — Failure requires a ladder

**Systems should degrade by shedding the optional to protect the
essential — and every recovery path must survive the failure it exists to
fix.**

*Root.* Fail-closed versus fail-open is a *consequence-asymmetry*
decision, not a preference: a door lock fails open (people outrank
property); a bank vault fails closed. Graceful degradation, load
shedding, circuit breakers, static stability — the whole resilience
canon — encode one idea: failure is a *state to be designed*, with a
ladder of degraded-but-defined modes, not an exception to be caught.
Hollnagel's Safety-II adds the positive corollary: systems mostly succeed
*because* humans and mechanisms adapt at the boundaries, so design the
adaptations. (Apollo's 1202 response, P4's counter-case, is this
principle executed under the highest possible stakes.)

*Case.* Cloudflare 2019 and CrowdStrike 2024 are the same lesson, five
years apart, from opposite directions. Cloudflare, July 2, 2019: a WAF
rule containing a catastrophic-backtracking regex was pushed globally
through a fast path that — unlike the standard deployment path — bypassed
staged rollout; CPU exhausted planet-wide within seconds, and the
response cost roughly 27 minutes of global degradation. CrowdStrike,
July 19, 2024: a content update — a channel file, not a binary — carried
a defect past a validator bug and deployed globally in one step,
blue-screening roughly 8.5 million Windows machines and disrupting
flights, hospitals, and banks; the vendor's own review drew the lesson
that sensor *binaries* had staged-deployment discipline and rapid-response
*content* did not. **The fast path is part of the system.** Every change
channel — rules, flags, content, config — needs the same ladder as the
slow path, because behavior does not check which pipeline changed it.

*Case, second.* Meta, October 4, 2021. A maintenance command withdrew the
backbone, DNS became unreachable, and — the structural lesson — the
recovery tooling, and reportedly even building badge access, depended on
the network that was down. Roughly six hours, in part because the paths
meant to fix the system lived inside the failure domain. For agent
platforms: the kill switch, the approval channel, and the audit trail
must not depend on the agent, the model provider, or the surface being
reviewed.

*Translation.* An agent's failure ladder is explicit: full function →
reduced evidence (declare coverage gaps, widen uncertainty, prefer
abstention) → advisory-only (verdicts flow, actions do not) → safe stop
(state persisted, episode intact, human notified). Timeouts, budget
exhaustion, tool failures, and model unavailability each map to a rung,
never to silence. Actions are idempotent so retries are safe; duplicate
timers and replayed webhooks are absorbed, not re-executed. And the
degraded modes are *rehearsed* — an untested fallback is a rumor about a
safety property (GitLab's five broken backup mechanisms, again).

*The test.* **"Show me the second-worst mode."** Systems with only two
modes — perfect and catastrophic — have chosen catastrophe as their
fallback.

---

### Principle 9 — Learning requires outcomes

**A system that never checks its verdicts against reality is not
learning; it is accumulating folklore with a database.**

*Root.* Goodhart's law (in Strathern's phrasing: when a measure becomes a
target, it ceases to be a good measure) governs any system graded on
proxies. The machine-learning literature adds two sharp warnings: hidden
feedback loops, where a model trained on outcomes it influenced launders
its own biases into "ground truth" (Sculley et al.'s technical-debt
catalog), and systematic miscalibration, where stated confidence and
observed correctness diverge unless explicitly measured and corrected
(Guo et al.). The scientific method is the antidote in institutional
form: prediction, controlled comparison, falsification, publication of
misses.

*Case.* Aviation's outcome flywheel is the standard to envy. ASRS — the
confidential, non-punitive incident reporting system NASA has operated
since 1976 — plus the mandatory-investigation regime for accidents,
produced a feedback loop that made commercial aviation's safety curve the
reference artifact for every other industry. The insight is
institutional: **outcomes were made cheap to report, safe to admit, and
mandatory to learn from.** Contrast any organization whose incident
reviews assign blame: its outcome data dries up within a quarter, and its
models calibrate on silence.

*Case, second.* Zillow Offers, 2021 — filed here, and not under
delegation, because the load-bearing failure was epistemic. A pricing
model's calibration broke under a fast-moving market regime; the company
compounded it with deliberately aggressive bidding; and — the textbook
feedback-loop clause — the program's own purchases fed the comparable-
sales environment it was calibrating against. The result: write-downs in
the hundreds of millions, roughly a quarter of the workforce cut, the
business line closed. The aggregate-authority lesson belongs to P7; the
root lesson belongs here: **a learning loop without independent ground
truth, checked on a cadence faster than the world changes, is a
confidence machine** — and without outcome labels you cannot tell a
correct verdict from a lucky one, an unnecessary pause from a prevented
incident, or a missed regression from a telemetry gap.

*Translation.* Every episode closes with an outcome label — immediate and
delayed — produced from ground truth *independent of the agent's own
verdicts* (a system must never grade itself with its own answers).
Verdict-versus-outcome joins feed calibration measurement per confidence
band; misses feed new discriminating checks; policy thresholds move on
evidence, through controlled one-variable experiments with paired
statistics, never through vibes after a bad week. Human labels outrank
machine labels and are never overwritten silently. And the flywheel is
product infrastructure with an owner — not an analytics project that dies
after the first quarter.

*The test.* **"When was this system last measurably wrong, and what
changed because of it?"** A system that cannot answer has either never
been wrong (false) or never looked (fatal).

---

### What we deliberately did not make a principle

Four candidates were argued and held out; recording why is part of being
arguable-with. **Tenancy and data boundaries** — who may learn from whose
episodes — is a governance commitment the platform must make explicitly
(the tenets and moat documents carry it as a first-class gap), but its
failure mechanism is P2/P3 applied at an organizational boundary, not a
new mechanism. **Agent identity and action attribution** — signing what
the agent *did*, not just what it read — is P2's envelope discipline
extended to actions, and belongs in the audit layer. **Explainability as
consumption** — AF447's deepest thread: the handover must be *legible
under stress*, not merely justified — is real, and owned by the
decision-experience work rather than a tenth principle. **Cost
governance** is a rung of P4's dial and a term in P7's ceilings. The
admission criterion is the same one that admitted P5–P9: a distinct
failure *mechanism*, not a distinct name. A future revision may promote
any of these if operating evidence shows the mechanism is distinct after
all.

---

## 3. Composition — the principles as a control structure

Leveson's frame makes the architecture obvious: each principle is a
*constraint layer*, and trustworthiness is the property of the whole
control structure, not of any component — least of all the model.

    trusted inputs (P5)  →  time-correct knowledge (P6)
        →  epistemic verdicts (P1)  ←  provenanced evidence (P2)
        →  owned state (P3)
        →  dialed authority (P4), bounded delegation (P7)
        →  laddered failure (P8)
        →  labeled outcomes (P9)  →  [feeds back into P1's calibration
                                       and P4's earned autonomy]

Two composition rules matter more than any single principle:

**The weakest-layer rule.** The layers are conjunctive — each is
necessary for the layers downstream of it to mean anything: perfect
provenance under an unbounded autonomy dial is a well-documented
catastrophe; a perfect dial acting on laundered evidence is a
confidently-authorized mistake. When any layer is weak, the system should
*downgrade adjacent layers* — lower autonomy when provenance is thin,
prefer abstention when inputs are suspect, shorten decision horizons when
state is contested. A control structure that cannot downgrade itself is a
single point of failure with extra steps.

**The earned-autonomy loop.** P9's outcome labels are what turn P4's dial
from a policy document into a *market*: autonomy is purchased with
calibration evidence, per action class, per service class — and is
repossessed on defined triggers (a metric regression past a pre-declared
floor, not a mood). This loop is the only legitimate mechanism for
autonomy expansion. Anything else — a demo went well, a customer asked, a
quarter ended — is Rasmussen's drift wearing a business case.

---

## 4. Objections, honestly handled

**"This is heavyweight. We need to ship."** The honest version of the
reply concedes more than the convenient one: an observe-and-recommend
agent (P4 levels 0–2) needs P1 and P2 hygiene *and* P5's structural
protections — because a read-only reviewer holds the full trifecta from
its first session, and a steered report that a human obeys is an
attack completed. What it can defer is the expensive upper machinery:
P4's execution rungs, P7's fleet controls, P9's full flywheel. Two things
make the bill payable: P5's protections are structural (sandboxing,
signed channels, credential custody) and amortize across every agent on
the platform; and the deferred machinery is deferred, not waived — it is
priced in before the first action rung, not after the first incident.
Knight Capital's 45 minutes erased years of velocity; the principles are
how you never have that day.

**"Models are getting smarter; most of this dissolves."** Some of it
genuinely might: better instruction-hierarchy training may shrink
injection susceptibility; better reasoning may improve hypothesis
quality. The part that cannot dissolve is structural, and the argument is
P2's own logic applied to the model itself: **a system's self-reported
trustworthiness is testimony, and testimony requires independent
verification.** A model's claim to be calibrated is checked by an
outcome record it does not control; its claim to resist injection is
checked by an adversarial harness outside itself; its authority is set by
a policy engine it cannot argue with. Verification independent of the
thing verified is not a limitation that intelligence outgrows — it is
what "trust" means.

**"Humans don't meet this bar either."** Correct — individual humans
don't. Institutions do, and that is the point: chain of custody, peer
review, double-entry books, flight rules, two-person integrity are the
*institutional technologies* humanity built because individual judgment,
however capable, does not scale trust. Agents do not get to skip the
institutional layer; they get to inherit it on day one, which is a gift
no human profession received.

**"This is just process — and process gets ritualized."** The first half
gets the easy answer: at scale, process *is* the product; nobody buys SRE
because reliability is exciting. The second half is the sharp version,
and it deserves respect rather than a slogan: review cards *do* decay
into checkbox theater, and Rasmussen's drift applies to safety processes
with exactly the same force it applies to everything else. So the
apparatus must monitor itself with the same discipline it imposes: track
the exemption rate on the review card ("does not apply" is a measurable
claim), audit a sample of exemptions each quarter, and treat a rising
rubber-stamp rate as a P9 signal about the process — a review process
that is never itself reviewed is folklore with a template.

---

## 5. The review card

Nine questions, one per principle. Any new capability, tool, or autonomy
expansion answers all nine or explains why one does not apply — and the
exemption rate is itself tracked (see the final objection above).

| # | Principle | The question |
|---|---|---|
| 1 | Verdicts require epistemics | What would change the system's mind, and is that recorded? |
| 2 | Evidence requires provenance | Can a skeptic reproduce every material claim from its envelope? |
| 3 | State requires ownership | Who owns each persistent fact, and how are stale writes detected? |
| 4 | Autonomy requires a dial | What is this action's worst case, and who explicitly accepted it? |
| 5 | Inputs require a trust boundary | If every input were attacker-authored, what is the worst outcome a consumer of the output would act on? |
| 6 | Knowledge requires a clock | As of when is each fact true, and when does the conclusion expire? |
| 7 | Delegation requires ceilings | Can any child path exceed the root's authority — and what is the fleet's worst correlated hour? |
| 8 | Failure requires a ladder | What is the second-worst mode, and has it been rehearsed? |
| 9 | Learning requires outcomes | When was the system last measurably wrong, and what changed? |

---

*Next: [02-rollout-reviewer-tenets.md](02-rollout-reviewer-tenets.md)
applies these principles to the Rollout Reviewer on the Ensemble
platform — what is already built, what is missing, and the rules for
evolving it. [03-value-and-moat.md](03-value-and-moat.md) derives the
commercial argument. [04-independent-critique.md](04-independent-critique.md)
records the adversarial review this document set was subjected to.*
