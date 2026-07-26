# Independent Critique — the Audit Record

**What this doc set was subjected to before anyone was asked to trust
it, what was found, what was fixed, and what remains open.**

*Docs 01–03 argue that verdicts need epistemics and claims need
provenance. This document is those principles applied to the documents
themselves: three independent adversarial reviews, run blind to each
other, with every finding dispositioned. If you are deciding how much to
trust this folder, start here.*

---

## 1. Method

Three critics, three non-overlapping mandates, run as independent agents
with no sight of each other's work, each instructed to assume claims
false until verified and told they earn credit only for catching errors:

| Critic | Mandate | Standard applied |
|---|---|---|
| **Fact-checker** | Every real-world incident, date, number, quote, and academic attribution in docs 01–03 | Own knowledge; verdicts CONFIRMED / CORRECT / SOFTEN / UNVERIFIABLE; instructed to flag paraphrase-presented-as-verbatim and figures that vary across sources |
| **Codebase-fidelity critic** | Every "the system does X today" claim, verified against both repositories with file:line evidence | Hard distinction between STRUCTURALLY ENFORCED (code rejects) and INSTRUCTED (prompt/skill text asks) — any instruction dressed as enforcement is a top-priority flag |
| **Logic critic** | Argument quality, internal consistency, cross-doc contradictions, case-to-principle fit, steelmanning of objections, rhetoric-vs-derivation | Distinguished-engineer bar; explicitly barred from fact-checking and code-checking to keep lanes independent |

All findings were then applied to the docs or explicitly declined with
reasons recorded below. Nothing was silently dropped.

## 2. Fact-check results

**Verdict: unusually accurate for the genre, with two flat academic
misquotes and a handful of hedging failures — all corrected.** Every
incident date checked out (TMI 1979, AF447 2009, Knight 2012-08-01,
GitLab 2017-01-31, S3 2017-02-28, Lion Air 2018/Ethiopian 2019,
Cloudflare 2019-07-02, Meta 2021-10-04, CrowdStrike 2024-07-19, Morris
1988, Apollo 1969, ASRS 1976, Pacioli 1494, Gettier 1963, Conant & Ashby
1970, Perrow 1984, PSW 2000, Zillow 2021, XZ 2024, SolarWinds 2020). The
mechanics of TMI, Knight, GitLab, S3, CrowdStrike, and Cloudflare were
rendered correctly, and two traps most documents fall into were
navigated (Strathern-vs-Goodhart attribution; Pacioli "codified" not
"invented").

Corrections applied:

1. **Conant & Ashby** — "must *contain* a model" was a flat misquote;
   the theorem (and the 1970 paper's title) is "must *be* a model."
   "Contain" is the later, distinct internal-model principle.
2. **Guo et al.** — misattributed "calibration decay"; their ICML 2017
   result is systematic *miscalibration* of modern networks. Reworded.
3. **Knight/Power Peg** — "defunct test module" traces to secondary
   retellings; the SEC order describes discontinued trading
   functionality unused since ~2003. Both loss figures now shown
   (~$440M company-reported pre-tax; >$460M per the SEC order).
4. **Plato/JTB** — "held for two millennia" is a contested textbook
   trope; softened to "often traced to Plato."
5. **Ashby** — his dictum is "only variety can *destroy* variety";
   "absorb" is Beer's popularization. Quoted correctly.
6. **Horizon** — first convictions overturned December 2020 (not 2021;
   2021 is the landmark Court of Appeal ruling); "hundreds" upgraded to
   the established "more than nine hundred" prosecutions.
7. **Apollo** — "radar misconfiguration" implied crew error; the
   cycle-stealing arose from a radar-interface fault. Corrected.
8. **Meta badge access** — press-reported, not in the official
   postmortem; now "reportedly."
9. **Zillow** — deliberate aggressive bidding compounded the model's
   calibration lag; causal framing widened accordingly.
10. **Willison's trifecta** — his third leg is "ability to externally
    communicate"; the doc's broader "any action channel" is now marked
    as our extension.

Retained with conscious hedges (fact-checker judged defensible):
CrowdStrike "roughly 8.5M" (Microsoft's estimate); Meta "roughly six
hours" (≈5¾); Morris worm "meaningful fraction" (conventional ~10%
estimate is itself rough); MCAS "~20-month grounding" (the FAA figure;
some regulators held longer). One claim flagged UNVERIFIABLE and kept as
internal doctrine, not external citation: T10's "scanner probes spike
during rollouts due to IP/LB reassignment" — operational heuristic
harvested from a practitioner source, not a published finding.

## 3. Codebase-fidelity results

**Verdict: the load-bearing safety claims are genuinely structural, not
prompt-hoped** — the recorder floor (verdict whitelist + server-side
policy re-run + `policy_conflict` rejection), min-samples abstention
with no path to pass below the floor, envelope signing with
scope-mismatch rejection at record time, dossier propose/promote with
the write tool structurally absent from the reviewer's surface,
precedent balance with policy evaluation consuming only envelopes (no
input path for precedent data), outcome labeling that never touches
agent verdicts, one-change enforcement, paired statistics, capability
projection with claimed-trust⇒ask, delegation clamps wired at the spawn
path, immutable registries, and the one-section twin diff — all verified
with file:line evidence. All eight gap-register entries were confirmed
as real gaps ("the register is the doc set's strongest credibility
asset; nothing in it needs retraction").

Six precision fixes were demanded and applied:

1. **The hitl variant belongs to incident-manager** — the rollout
   reviewer ships scripted-only. T6 and the moat table now name the
   demonstrating agent instead of implying the reviewer has it.
2. **"≥3 supporting episodes" gates machine promotion *suggestions*,
   not promotion** — humans promote with no support-count check, by
   design. Reworded in T8 and the moat table.
3. **"Human labels outrank machine labels" was half-true** — labels are
   write-once for everyone; a human outranks the collector only by
   labeling first. Reworded; the explicit human-override path added to
   G4's closure contract.
4. **Replay overclaim** — what exists is bitemporal retrieval replay +
   verdict-vs-label scoring + fixture-armed sessions; full checkpoint
   re-execution over stored decision-time evidence is the G4-era
   design. §9 now says exactly that.
5. **"Bitemporal episodes" misattributed** — bitemporality belongs to
   the dossier journal and time-correct retrieval; the
   episode/checkpoint store is append-only. Fixed in T4 and doc 03.
6. **Security precision** — the HMAC key is symmetric and shared
   between exactly two server processes, with a dev-default that
   production MUST override; the advisory `evaluate_policy` tool is
   scope-unchecked (only the recording path enforces); "no shell"
   sharpened to "no shell tool" (the slim image contains `/bin/sh`; the
   agent is granted no tool that reaches it).

Implementation footnotes recorded, not doc-changed (doc 01 is normative,
and these note where implementation currently approximates the norm):
budget "fractions that provably sum below the parent's ceiling" is
implemented as fraction-of-remaining-at-spawn-time — concurrent spawns
against the same snapshot are not jointly summed; ladder termination is
scheduled by rollout-intel while the relay fires it (T4 wording updated).

## 4. Logic-critique results

**Verdict quoted in full honesty:** *"well above the median for
documents of its genre… but it does not yet clear the
distinguished-engineer bar, because its failure mode is precisely the
one it lectures others about: rhetoric presented in the grammatical form
of derivation."* 34 findings. The five structural ones, and their
resolutions:

1. **Misfiled flagship cases.** Zillow was filed under delegation
   ceilings when its load-bearing failure is a learning loop without
   independent ground truth (with a feedback-loop clause); CrowdStrike
   was filed under time-correctness when its postmortem lesson is
   staged-rollout discipline on the fast path. → Zillow moved to P9,
   Morris worm promoted to P7's case slot, CrowdStrike merged with
   Cloudflare under P8; P6 rebuilt around an honestly-marked pattern
   case with an explicit argument for separate billing.
2. **Incoherent moat mathematics** — multiplication disclaimed, then a
   min-rule, then a third criterion, and a roadmap following none of
   them; taken literally the equation implied the moat was ~zero today.
   → Rewritten (§5): tier-dependent factor sets (Reviewer ships without
   topology; Guardian doesn't), one explicit investment rule, and §11
   resequenced under a stated rule that matches its own quarters.
3. **The DIY baseline proved the wrong thing** — vanilla-prompt-on-
   Ensemble measures skill content while inheriting the disputed trust
   machinery for free; the buyer's actual counterfactuals were missing.
   → Three-arm design: policy-pack-only (arm 0), raw-tools DIY (arm 1),
   vanilla-on-Ensemble (arm 2); results shared with design partners.
4. **The velocity objection was won by shrinking the standard** —
   claiming advisory agents need "only P1/P2 hygiene" while P5's own
   argument shows the read-only reviewer holds the full trifecta from
   session one. → Rewritten to concede P5 from day one, priced as
   structural and amortized.
5. **Tighten-only's cost was unpriced and its sanctioned direction is
   an attack channel** — adversarial tightening / evidence starvation
   as deployment denial-of-service. → T1 now prices the trade and names
   its dethroning statistic; P5 carries the availability attack and its
   detection response; P5's test extended beyond "it executes
   something" to steered-report harm.

Also applied: the extended failure chain (nine cut-points, matching the
claim); the honest re-scaffolding of why P5–P9 exist; P5's evidence
labeled structural-not-actuarial; the tenancy/learning boundary (G9 +
doc 03 §6 scoping); gates given numeric floors, named sign-offs, and
auto-revoke triggers; Gate C's calibration-curve circularity removed;
G5 scheduled; T9's commercial motive named candidly; ritualization
answered with the exemption-rate KPI; aphorism density cut (including
the "moat wink" and the special-forces bumper sticker); the six-verbs
arithmetic fixed.

Declined or deferred, with reasons: a glossary pass for
platform-internal vocabulary in doc 02 §0 (deferred — terms are
contextualized inline; revisit if outside readers stumble); collapsing
P5/P6 into the original four (declined — the cross-cutting-concern
argument is now made explicitly in P6, and P5's composition status is
owned in its text); trimming the flywheel's triple narration across the
three docs (retained deliberately — each doc is read standalone).

## 5. Standing positions relative to the source standard

Recorded so nobody mistakes extension for agreement-by-silence:

- **The autonomy ladder (0–6) is the standard's own construct**, adapted
  from Parasuraman/Sheridan/Wickens and SAE J3016 precedents — useful,
  but not an industry standard; docs 01–02 use level *names* rather than
  claiming standardized numbers.
- **The moat equation is retained as rhetoric, replaced as math** — doc
  03 §5 extracts its two true claims (tier-dependent necessity;
  conjunction within a tier) and states an actual decision rule.
- **"MUST never emit a verdict as an isolated label"** is affirmed as
  the goal and honestly gapped: today's implementation carries verdict +
  reasoning + report with bundle-level evidence linkage; claim-level
  structure is G1, scheduled first.
- **The standard's five-layer moat stack** is adopted with maturity
  grades attached — layer 1 (context graph) is thinner today than the
  standard's prose implies for us, and doc 03 says so.

## 6. What remains open

- The docs have passed machine adversarial review, not human
  distinguished-engineer review — the bar they aim at. The next
  reviewer should start from this file and try to break §4's
  resolutions.
- Figures retained with hedges (§2 above) should be re-verified against
  primary sources before any *external* publication.
- G-register items are commitments the docs now lean on (G1 for the
  audit story, G4 for every learning claim, G9 for tenancy) — if a
  quarter passes without movement, the honest move is to weaken the
  dependent claims, not to let them ride.
- The three-arm baseline (doc 03 §9) is designed but not yet run; until
  arm 0 (policy-pack-only) is measured, the marginal value of the model
  itself over the deterministic floor remains an argued, not
  demonstrated, claim.

## 7. Maintenance rules for this folder

1. Any new real-world claim enters with a source and survives a
   fact-check pass, or ships hedged.
2. Any new "the system does X" claim names its mechanism; the
   structural-vs-instructed distinction is load-bearing — never present
   instruction as enforcement.
3. Any change to tenets, gates, or the gap register updates this file's
   §6 dependencies in the same commit.
4. Re-run the full three-critic review after any major revision, and
   append — never overwrite — the findings here. This file is
   append-only by policy; it is the folder's provenance envelope.
