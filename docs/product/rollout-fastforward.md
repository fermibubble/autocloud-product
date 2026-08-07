# Rollout Fast-Forward — Mathematical Design Reference

### Temporal rollout review: run tomorrow before you ramp today

> **Scope.** Fast-Forward compiles a deploy's change set into a ranked
> family of delayed-failure hypotheses, selects a budget- and
> deadline-feasible experiment portfolio, estimates failure trajectories
> with robust statistics, applies a sequential three-decision stopping
> rule, and emits either a replayable temporal counterexample or an
> explicitly qualified future envelope. This document states the
> mathematics precisely: definitions, derivations, and propositions with
> proofs, each tied to the module that implements it.

**Version 3.0 · August 2026 · Status: implemented (MVP, Phases 0–2)**

Labels used throughout: **implemented** (the exact formula in the code,
module named), **roadmap** (specified by the research standard; the code
leaves a marked seam). Numeric constants are collected in Appendix A.
Companion documents: [rollout-reviewer.md](rollout-reviewer.md) and the
implementation under `fastforward/rollout_fastforward/`.

---

## Contents

- [1. System model and invariants](#1-system-model-and-invariants)
- [2. The operational-age space and first divergence](#2-the-operational-age-space-and-first-divergence)
- [3. Change canonicalization and hash-based identity](#3-change-canonicalization-and-hash-based-identity)
- [4. The hazard floor as a monotone operator](#4-the-hazard-floor-as-a-monotone-operator)
- [5. Experiment selection: the portfolio problem and its greedy reduction](#5-experiment-selection-the-portfolio-problem-and-its-greedy-reduction)
- [6. Robust estimation theory](#6-robust-estimation-theory)
- [7. Branching processes and retry amplification](#7-branching-processes-and-retry-amplification)
- [8. Fluid queue dynamics and threshold-crossing times](#8-fluid-queue-dynamics-and-threshold-crossing-times)
- [9. Reference envelopes and standardized deviation](#9-reference-envelopes-and-standardized-deviation)
- [10. The signal test as a composite hypothesis test](#10-the-signal-test-as-a-composite-hypothesis-test)
- [11. Probe protocols and their decision functionals](#11-probe-protocols-and-their-decision-functionals)
- [12. The sequential stopping rule](#12-the-sequential-stopping-rule)
- [13. Fidelity aggregation](#13-fidelity-aggregation)
- [14. Outcome derivation: a total precedence function](#14-outcome-derivation-a-total-precedence-function)
- [15. Determinism and replay](#15-determinism-and-replay)
- [16. Evidence integrity: hash binding and HMAC](#16-evidence-integrity-hash-binding-and-hmac)
- [17. Evaluation metrics and calibration](#17-evaluation-metrics-and-calibration)
- [Appendix A. Constants](#appendix-a-constants)
- [Appendix B. Statistical limitations, stated precisely](#appendix-b-statistical-limitations-stated-precisely)

---

## 1. System model and invariants

The runtime context. A deploy event `E` for service `s` carries a
change manifest `M` (§3). The relay creates a review episode and issues
Fast-Forward a single request `(E, s, T_d, B)` where `T_d` is the
deadline (seconds until the T+30 decision checkpoint) and `B` a budget
(step count and probe wall-time). Fast-Forward runs asynchronously and
terminates in one of the states

```
COMPLETED, COUNTEREXAMPLE, BUDGET_EXHAUSTED, UNSUPPORTED, CANCELED
```

with an outcome in the six-element set

```
Ω = { temporal_counterexample, bounded_future_envelope,
      projected_boundary, unsupported_temporal_risk,
      no_material_temporal_hazard, inconclusive_budget }.
```

Results re-enter the review as cryptographically signed evidence
envelopes (§16), consumed by a deterministic policy rule at T+30
(§14.2).

Design invariants, each of which is given mathematical content later:

1. **No self-scheduling.** Fast-Forward possesses no clock authority;
   `T_d` and `B` are exogenous inputs.
2. **Signed evidence only.** The verdict path is a function of
   verified envelopes exclusively; verification failure is equivalent
   to absence (§16.3).
3. **Determinism.** The entire pipeline is a composition of pure
   functions of `(M, seed-derivation)`; see Proposition 15.1.
4. **Monotone conservatism.** External proposals can only enlarge the
   hazard set (Theorem 4.1); budget exhaustion and infrastructure
   failure map to non-passing outcomes under every rule (Propositions
   12.1 and 14.1).
5. **Qualified claims only.** A passing claim requires the fidelity
   gate predicate (§13.3); otherwise the outcome is demoted (§14.1,
   rule 7).

---

## 2. The operational-age space and first divergence

### 2.1 The age space

**Definition 2.1 (operational age).** Let the *age space* be

```
A = ℝ₊ × ℕ⁸ ∋ a = (t_wall, N_req, N_write, N_retry, N_expiry,
                    N_schedule, N_compact, N_conn, N_turn)        (A1)
```

with the componentwise partial order `a ≤ a′ ⇔ aᵢ ≤ a′ᵢ ∀i`. Each
coordinate is an independent counter ("axis"). `(A, ≤)` is a lattice:
meets and joins exist componentwise.

Elapsed wall-clock time is one coordinate among several. A failure
mechanism is associated with the minimal set of axes whose advancement
drives it; e.g. a per-lifecycle resource leak depends on `N_conn` and
is invariant under advancement of `t_wall` alone.

**Implemented axes** (counters of `sim/probe_target.py`, each
independently advanceable): `cycles`, `requests`, `retries`,
`cred_age_s`, `rotations`, `wall_s`.

### 2.2 Trajectories and the first-divergence functional

A probe induces a *drive sequence*: a finite sequence of operations
whose cumulative effect is a nondecreasing path
`a₀ ≤ a₁ ≤ … ≤ a_n` in `A`. Along this path the candidate and stable
systems define observable processes `X_c(a_k)` and `X_s(a_k)`
(counter vectors, event indicators).

**Definition 2.2 (first divergence).** Given a divergence functional
`D : X × X → ℝ₊` and tolerance `τ > 0` fixed *a priori*,

```
a* = inf { a_k : D( X_c(a_k), X_s(a_k) ) > τ }.                   (A10)
```

Because the drive sequence is a finite totally ordered chain in `A`,
the infimum is attained at the first index satisfying the predicate
(or is `+∞` when no index does); no topological subtlety arises.

**Remark 2.3 (pre-registration of τ).** τ is a function of the hazard
and policy only — never of the observed candidate data. This is the
standard pre-registration requirement: a data-dependent τ would make
the event `{D > τ}` non-measurable with respect to the information
available at design time and would invalidate the error-rate
reasoning of §12.

**Instances of `(D, τ)`** (one per playbook, §11):

| Playbook | `D` | τ |
|---|---|---|
| resource_lifecycle_v1 | robust standardized per-round growth rate (Definition 9.2) | z = 3 |
| rate_balance_v1 | joint predicate on offspring mean and queue drift (§11.2) | (m ≥ 1) ∧ (L_Q > 0) |
| cred_lifecycle_v1 | counting functional `stale_reuse_count` | 0 (exact) |

---

## 3. Change canonicalization and hash-based identity

### 3.1 Canonical form

**Definition 3.1.** A manifest is a finite multiset of items
`(kind, name, from, to, paths)`, `kind ∈ {code, dependency, config,
flag, schema}`. Its *canonical form* `C(M)` sorts items by the key
`(kind, name)` and serializes with lexicographically sorted JSON keys
and fixed separators. (`rollout_fastforward/manifest.py`.)

**Proposition 3.2 (well-definedness).** `C` is invariant under
permutation of the item list and of JSON key order; hence any two
descriptions of the same change have equal canonical byte strings.

*Proof.* Sorting by a total key on items removes list-order freedom
(ties are impossible for distinct items under `(kind, name)`
uniqueness; equal items are identical). Serializing with sorted keys
removes object-order freedom. The composition eliminates all
serialization degrees of freedom, so the byte string is a class
invariant. ∎

### 3.2 Digest and collision bounds

The digest is `d(M) = "mf_" ‖ H₆₄(C(M))` where `H₆₄` denotes SHA-256
truncated to 64 bits (16 hex characters).

**Proposition 3.3 (collision probability).** Modeling `H₆₄` as a
uniform random function into `{0,1}⁶⁴`, the probability that any two
of `n` distinct manifests collide satisfies the birthday bound

```
P(collision) ≤ n(n−1) / 2⁶⁵.
```

For `n = 10⁶` manifests, `P ≤ 2.8 × 10⁻⁸`. Collision resistance at
this truncation is adequate for identity (not for adversarial
commitment; the *security* boundary uses full-width HMAC, §16). ∎

### 3.3 Feature extraction

Items map to a finite trait alphabet via substring predicates on
lowercased names/paths (classes `dep-class:{pool, auth, http, retry,
db}`, `cfg-class:{retry, timeout, ttl, expiry, pool, queue, batch,
cache}`, `code-touch:{connection, auth, retry, queue, schedule,
cache}`, plus literal `dep:`, `cfg:`, `flag:`, `schema:` traits). The
trait map `Φ(M) ⊆ Σ_traits` is deterministic; the fixture manifest of
the control service `demo-healthy` satisfies `Φ(M) ∩ Σ_hazard = ∅` by
construction, which yields a zero-cost null path through the entire
pipeline (§14, rule 4).

### 3.4 Hazard identity

```
hazard_id(h) = "hz_" ‖ H₆₄( class(h) ‖ "|" ‖ sort(Φ_h) ‖ "|" ‖ d(M) )
```

**Proposition 3.4.** `hazard_id` is a pure function of
`(class, matched traits, manifest)`; therefore equal changes yield
equal hazard identifiers. Combined with Proposition 15.1 this extends
to equality of derived seeds and counterexample identifiers. ∎

---

## 4. The hazard floor as a monotone operator

The compiler (`rollout_fastforward/compiler.py`) evaluates a fixed
signature table (six classes with importance weights
`r ∈ {0.90, 0.85, 0.90, 0.60, 0.50, 0.50}`; see Appendix A) producing
the *floor set* `F(M) = { h₁, …, h_k }`, each `hᵢ` carrying
`relevance(hᵢ) ∈ (0,1]`.

External proposals (e.g. from an LLM) are admitted through the merge
operator only.

**Definition 4.1 (merge).** Let `P` be a finite set of proposals, each
either a new hazard or a re-weighting of an existing id. Define

```
merge(F, P) = F ∪ { p ∈ P : id(p) ∉ id(F) },
relevance′(h) = max( relevance_F(h), relevance_P(h) )   for h ∈ F.
```

**Theorem 4.2 (monotone conservatism).** For every proposal sequence
`P₁, …, P_n`, writing `F₀ = F(M)` and `Fⱼ = merge(Fⱼ₋₁, Pⱼ)`:

1. `F₀ ⊆ F₁ ⊆ … ⊆ F_n` (the hazard set is nondecreasing);
2. for every `h ∈ F₀`, `relevance` is nondecreasing in `j`;
3. `merge` is idempotent (`merge(F, ∅) = F`, `merge(merge(F,P),P) =
   merge(F,P)`) and order-insensitive over proposals with distinct ids.

*Proof.* (1) `merge` is defined via set union; unions are extensive.
(2) `relevance′ = max(·,·)` and `max` is monotone in its first
argument with `relevance′ ≥ relevance`. Induction over `j` gives a
nondecreasing sequence. (3) Union and pointwise max are idempotent and
commutative/associative over disjoint key sets. ∎

**Corollary 4.3 (adversarial robustness).** No adversarially chosen
proposal sequence can remove a floor hazard or reduce a floor
relevance. Hence the deterministic detection guarantee of the
signature table is a lower bound on system suspicion under arbitrary
model behavior. (Unit-tested property.)

**Roadmap: the calibrated ranker.** The research standard replaces the
constant relevance weights by the posterior

```
P(h | x) = σ( β₀,ₕ + βₕᵀ φ(x) + log( πₕ / (1 − πₕ) ) ),            (A2)
```

a logistic model in features `φ(x)` with service-class prior odds
`πₕ/(1−πₕ)` entering as an intercept offset (the standard
log-odds/logit decomposition: `σ(z) = 1/(1+e^{−z})`, and
`σ(logit(π) + βᵀφ) ` is Bayes-consistent updating of the prior under a
log-linear likelihood ratio). Fitting requires labeled outcomes; the
join keys exist (§17.3).

---

## 5. Experiment selection: the portfolio problem and its greedy reduction

### 5.1 The exact problem (roadmap)

Each candidate experiment `e` for hazard `h` has utility

```
U(e,h) = P(h|x) · I_h · D(e,h) · S(e) · F(e) − λC(e) − μT(e)      (A3)
```

(detection power `D`, decision sensitivity `S`, fidelity `F`, cost `C`,
time `T`), and the planner solves the 0–1 program

```
max_{z_e ∈ {0,1}}  Σ_e z_e ΔR(e)
s.t.   Σ_e z_e C(e) ≤ B,    Σ_e z_e T(e) ≤ T_d.                    (A4)
```

**Remark 5.1 (hardness).** (A4) contains the 0–1 knapsack problem as
the special case of one constraint, hence is NP-hard (reduction from
subset-sum). With two resource constraints it is a 2-dimensional
knapsack; exact solution is exponential in general.

### 5.2 The implemented reduction

The MVP objective degenerates: relevance is a single scalar per hazard
(§4), each hazard admits at most one cheap (signal) and one expensive
(probe) experiment with fixed cost estimates
`C_sig = 5 s`, `C_probe = 30 s` (doubled to `60 s` when no stable
profile exists, since a paired baseline run is then required, §9.4).
Under these restrictions the following greedy is used
(`rollout_fastforward/planner.py`):

1. Impose the strict total order `h ≺ h′ ⇔ (−r_h, id_h) <
   (−r_{h′}, id_{h′})` (lexicographic; total because ids are unique).
2. For each hazard in order: emit its signal step if one exists;
   attach its probe step with guard `run_if = [signal inconclusive]`.
3. While estimated cost exceeds the deadline-derived limit, delete the
   ≺-maximal (least important) step and mark its hazard *unresolved*.
4. Enforce the step-count budget `|steps| ≤ B_steps` identically.
5. Terminate all remaining steps upon the first high-impact
   counterexample (`stop_all_if`): once a decision-changing failure is
   confirmed, the marginal decision value of every remaining
   experiment is zero, so continuing has strictly negative utility
   under (A3).

**Proposition 5.2 (optimality of the reduction).** If (i) all steps of
a mode have equal cost, (ii) the objective is the importance-weighted
count of resolved hazards with importance treated lexicographically
(resolve more-important hazards first), then the greedy of steps 1–4
returns an optimal feasible plan.

*Proof sketch.* With uniform costs, feasibility depends only on the
number of retained steps of each mode; among plans retaining `k`
steps, the lexicographic objective is maximized by retaining the `k`
≺-minimal ones, which is exactly what tail-deletion from a ≺-sorted
list produces. ∎

**Remark 5.3 (honest trimming).** Deleted steps are not silently
dropped: each marks its hazard unresolved, which forces the terminal
outcome into `unsupported_temporal_risk` (§14.1, rule 3). Formally,
the planner's feasibility projection is *coverage-accounting*: the
claimed coverage set always equals the executed set.

The plan is fingerprinted: `plan_digest = H(canonical ordered
(hazard_id, mode, template) list)`, frozen in the decision-time
snapshot; auditability of *selection*, not only of results.

---

## 6. Robust estimation theory

Probe series are short (`n ≤ 8` rounds) and contaminated (warm-up
transients, GC pauses, scheduler noise). All estimators are therefore
chosen for high breakdown point rather than efficiency.
(`rollout_fastforward/stats.py`.)

### 6.1 Breakdown points

**Definition 6.1 (finite-sample breakdown point).** For an estimator
`T_n` on samples of size `n`, the breakdown point is

```
ε*_n(T) = min { m/n : sup over corruptions of m points of |T_n| = ∞ }.
```

**Proposition 6.2.** The sample mean has `ε*_n = 1/n → 0`; the sample
median has `ε*_n = ⌈n/2⌉/n → 1/2`.

*Proof.* One unbounded point moves the mean unboundedly (linearity).
For the median: as long as strictly more than half the points remain
in a compact set, the middle order statistic remains within that set;
corrupting ⌈n/2⌉ points can place the middle order statistic
arbitrarily. ∎

### 6.2 Quantiles

Sample quantiles use the linear-interpolation estimator (Hyndman–Fan
type 7): for sorted `s₀ ≤ … ≤ s_{n−1}`,

```
Q_q = s_i (1 − γ) + s_{i+1} γ,   where  i = ⌊q(n−1)⌋,  γ = q(n−1) − i.
```

### 6.3 The Theil–Sen slope estimator

**Definition 6.3.** For points `(x₁,y₁), …, (x_n,y_n)` with distinct
abscissae, define the pairwise slope multiset
`S = { (y_j − y_i)/(x_j − x_i) : i < j }` (|S| = C(n,2)) and

```
β̂_TS = median(S).
```

**Proposition 6.4 (consistency / unbiasedness under symmetry).** In
the model `y_i = α + βx_i + ε_i` with i.i.d. errors symmetric about 0,
each pairwise slope equals `β + (ε_j − ε_i)/(x_j − x_i)`, whose noise
term is symmetric about 0; hence the population median of pairwise
slopes is `β`, and `β̂_TS` is a consistent, median-unbiased estimator
of `β`. ∎

**Theorem 6.5 (breakdown point).** `ε*(β̂_TS) = 1 − 1/√2 ≈ 0.2929`
asymptotically.

*Derivation.* If a fraction `ε` of the points is corrupted, the
fraction of pairs with both endpoints clean is `(1−ε)²` (up to
`O(1/n)`). The median of `S` is controlled by clean pairs iff clean
pairs form a strict majority:

```
(1 − ε)² > 1/2  ⇔  1 − ε > 2^{−1/2}  ⇔  ε < 1 − 1/√2.  ∎
```

With `n = 8` rounds, two corrupted rounds (25 %) remain below the
threshold and are absorbed.

**Numerical check.** Points `(1,10), (2,12), (3,14), (4,16), (5,100)`
(true `β = 2`, one gross corruption). The ten pairwise slopes sort to
`[2,2,2,2,2,2, 22.5, 29.33, 43, 84]`, so `β̂_TS = 2` exactly, while
the least-squares slope is `Σ(x−x̄)(y−ȳ)/Σ(x−x̄)² = 184/10 = 18.4`.
(This contrast is a unit test, with heavy-tailed noise added.)

**Interval.** The implementation reports
`[L, U] = [Q_{0.05}(S), Q_{0.95}(S)]`, the central 90 % of the
pairwise-slope distribution. **Remark 6.6 (relation to Sen's CI).**
The classical distribution-free Theil–Sen interval selects order
statistics of `S` at ranks `M/2 ∓ z_{α/2}·σ_S/2` where `σ_S²` is the
null variance of Kendall's `S`-statistic; the implemented percentile
band is a simplification that widens with contamination (a desirable
direction) but carries no finite-sample coverage theorem, and no
correction for sequential examination. Both limitations are stated
precisely in Appendix B.1.

### 6.4 MAD and the consistency constant

**Definition 6.7.** `MAD(v) = median_i | v_i − median(v) |`.

**Derivation 6.8 (the constant 1.4826).** Let `X ~ N(μ, σ²)` and let
`m` denote the population MAD: `P(|X − μ| ≤ m) = 1/2`. Then

```
P(|X − μ| ≤ m) = 2Φ(m/σ) − 1 = 1/2  ⇒  Φ(m/σ) = 3/4
⇒  m = σ · Φ⁻¹(3/4) = 0.67449 σ
⇒  σ = m / Φ⁻¹(3/4) = 1.4826 m.
```

Hence `σ̂ = 1.4826 · MAD` is a Fisher-consistent scale estimator at
the normal model, with breakdown point 1/2 (inherited from the two
nested medians). The implementation guards `σ̂ ≥ ε = 10⁻⁹`.

**Definition 6.9 (robust standardization).**
`z(x) = (x − median) / max(1.4826 · MAD, ε)`.

**Proposition 6.10 (tail guarantees for the threshold z = 3).**
(i) Under normality, `P(|z| > 3) = 2(1 − Φ(3)) ≈ 0.0027`.
(ii) Distribution-free, for any distribution with finite variance,
Chebyshev's inequality gives `P(|z_σ| > 3) ≤ 1/9`, where `z_σ` is the
σ-standardized score. The system never converts a single `z`
exceedance into a terminal decision — it marks the divergence *index*
(§11.1); terminal decisions require the entire slope interval to clear
a threshold (§12). ∎

### 6.5 The Huber location estimator

**Definition 6.11.** With scale `σ̂` fixed, the Huber M-estimator
minimizes `Σᵢ ρ_k( (vᵢ − μ)/σ̂ )` where

```
ρ_k(r) = r²/2           for |r| ≤ k,
ρ_k(r) = k|r| − k²/2    for |r| > k,          k = 1.5.
```

**Derivation 6.12 (IRLS form).** The estimating equation is
`Σ ψ_k(rᵢ) = 0` with `ψ_k = ρ_k′`, i.e. `ψ_k(r) = r` for `|r| ≤ k`
and `k·sign(r)` otherwise. Writing `ψ_k(r) = w(r)·r` with

```
w(r) = min( 1, k/|r| )
```

turns the equation into the weighted-mean fixed point
`μ = Σ w(rᵢ) vᵢ / Σ w(rᵢ)`, iterated from `μ₀ = median` (≤ 20
iterations). Since `ρ_k` is convex and the iteration is a
majorize–minimize step for fixed `σ̂`, the objective is non-increasing
and the iteration converges to the unique minimizer. ∎

`k = 1.5` yields ≈ 95 % asymptotic efficiency at the normal model
while bounding the influence function at `k·σ̂`.

---

## 7. Branching processes and retry amplification

### 7.1 The attempt tree

Model request execution under retries as a Galton–Watson branching
process whose nodes are *attempts*: an attempt fails with probability
`p_f`; upon failure it spawns `K` retry attempts (`E[K] < ∞`), each
the root of an i.i.d. subtree.

**Definition 7.1 (offspring mean).** The expected number of children
of an attempt is

```
m = p_f · E[K].                                                    (A8)
```

**Theorem 7.2 (expected total attempts).** Let `T` be the total number
of attempts generated by one arrival. If `m < 1`,

```
E[T] = 1 / (1 − m),
```

and if `m ≥ 1` (with `P(K ≥ 1 | fail) > 0` non-degenerate),
`E[T] = ∞`.

*Proof.* By the tree recursion, `T = 1 + Σ_{j=1}^{κ} T_j` where `κ` is
the (random) number of children of the root and the `T_j` are i.i.d.
copies of `T` independent of `κ`. Wald's identity gives
`E[T] = 1 + E[κ]·E[T] = 1 + m·E[T]`; solving yields `E[T] = 1/(1−m)`
when `m < 1`. When `m ≥ 1` the generation sizes satisfy
`E[Z_g] = m^g`, so `E[T] = Σ_g E[Z_g] = Σ_g m^g` diverges. ∎

**Corollary 7.3 (criticality).** `m` is a sharp phase boundary: total
expected work per arrival is `1/(1−m)` (bounded) in the subcritical
regime and unbounded in the critical/supercritical regime. E.g.
`m = 0.5 ⇒ E[T] = 2`; `m = 0.9 ⇒ E[T] = 10`; `m = 1.2` (the seeded
`p_f = 0.3, E[K] = 4` fixture) ⇒ divergent, with generation sizes
`100, 120, 144, 172.8, …` from 100 initial failures.

**Remark 7.4 (why m is measured, not computed).** The configured
`retry_max` upper-bounds `K` but the effective `E[K]` and `p_f` depend
on backoff, jitter, retry budgets and failure correlation in the
actual code path. The probe therefore estimates `m̂` empirically as
(observed retries)/(observed failures) under a dialed dependency
failure rate (§11.2). The decision couples `m̂ ≥ 1` with an observed
queue-drift condition, because supercritical branching with adequate
drain capacity does not accumulate (see §8).

---

## 8. Fluid queue dynamics and threshold-crossing times

### 8.1 The fluid limit

For a queue with arrival rate `λ(t)` and service rate `μ(t, Q)`, the
fluid (functional-law-of-large-numbers) approximation of the queue
length is the ODE

```
dQ/dt = λ(t) − μ(t, Q).                                            (A7)
```

On any interval where both rates are constant with `λ > μ`, the
solution is affine, `Q(t) = Q₀ + (λ − μ) t`, and the threshold-crossing
time is

```
T_fail = (Q_max − Q₀) / (λ − μ).
```

**Remark 8.1 (validity).** The affine form holds only while (i) the
rates are stationary and (ii) no nonlinear control boundary
(autoscaling, backpressure, load shedding) is crossed. The probe
accordingly estimates the *net drift* `λ − μ` directly as the robust
slope of observed queue depth (Definition 6.3) rather than composing
separately estimated rates, and escalation to probe from signal is
mandatory whenever nonlinearity is suspected (research standard,
Part V).

### 8.2 General threshold-crossing (resource form)

For a resource following `R(n) = R₀ + βn + ε_n` in operation count
`n`, with production operation rate `q` (operations/minute):

```
T_fail = (R_max − R_now) / ( β̂ · q )   [minutes],
T_fail = 0        if R_now ≥ R_max,
T_fail = ∞        if β̂ ≤ 0 or q ≤ 0.                              (A6)
```

Dimensional analysis: `[handles] / ([handles/op] · [op/min]) = [min]`.
The rate `q` must be the rate of the *β-relevant* operation (lifecycle
rate for a per-lifecycle leak), not total request rate; using a
different rate changes the answer by the ratio of the two rates.

**Numerical check** (demo-leak): `R_max = 1000`, `R_now = 46`,
`β̂ = 0.03` handle/cycle, `q = 60` cycle/min ⇒
`T_fail = 954/1.8 = 530 min ≈ 8.8 h`.

---

## 9. Reference envelopes and standardized deviation

### 9.1 Stable profiles

**Definition 9.1.** A *stable profile* for (service, template,
environment) is the triple of robust sufficient statistics per
measurement:

```
π = { metric ↦ ( median_s, MAD_s, n_s ) }.
```

(`rollout_fastforward/profiles.py`.) Profiles carry an expiry time
(`created_at + 14 d`) and an environment fingerprint
`(runtime, spec_digest)`; a profile is *usable* iff unexpired and
fingerprint-equal to the probe environment. Unusable ⇒ treated as
absent.

### 9.2 Candidate standardization

**Definition 9.2.** The candidate deviation for measurement `θ̂_c` is

```
Z = ( θ̂_c − median_s ) / ( 1.4826 · MAD_s )
```

(Definition 6.9 applied with the profile's statistics).

**Remark 9.3 (relation to the two-sample statistic).** The research
standard's form is the Welch-type statistic

```
Z_W = ( θ̂_c − μ_s ) / √( σ̂_c²/n_c + σ_s²/n_s ),
```

which accounts for sampling error on both sides. The implemented
one-sample robust form treats the profile as a fixed reference
(justified when `n_s ≫ n_c`, here 42 ≫ 8, so the reference's standard
error contributes `O(√(n_c/n_s))` relative correction) and replaces
moment estimates by median/MAD for breakdown-point reasons
(Proposition 6.2, Derivation 6.8). Roadmap: restore the two-sample
denominator with robust scale estimates once probe series lengthen.

### 9.3 Absence semantics

**Proposition 9.4 (no default pass).** In every consumer of a profile
(signal §10, playbooks §11), the absent-profile branch returns
`inconclusive`-typed results, and by the outcome precedence (§14.1,
rule 3) any inconclusive disposition excludes the passing outcomes.
Hence there exists no execution path on which a missing reference
produces `bounded_future_envelope` or a rule-level pass. ∎
(Verified by unit tests per module.)

### 9.4 Paired-baseline fallback

When the profile is absent but the previous revision's clean spec is
available, the playbook constructs the reference by running the
identical drive (same seed, same rounds) against the clean spec and
computing `(median, MAD, n)` of the same measurement. This is a
matched-pairs design: both arms share the drive sequence and seed, so
the reference differs from the candidate only in the treatment (the
spec), eliminating drive-sequence variance from the comparison.

---

## 10. The signal test as a composite hypothesis test

Signal mode (`rollout_fastforward/signals.py`) tests telemetry slopes
without executing the candidate. Let `β` denote the true post-deploy
slope of the primary metric, and let the stable profile induce the
standardization `z(·)` of Definition 9.2 on slopes.

### 10.1 Formulation: three-decision testing with an indifference zone

The problem is the classical three-decision formulation:

```
H_harm : β ≥ β_harm      (breach within horizon)
H_safe : β ≤ β_safe      (within envelope)
indifference zone: β ∈ (β_safe, β_harm) — either decision acceptable,
                   but the honest report is "cannot yet distinguish".
```

The test statistic is the interval `[L, U]` of §6.3 mapped through
`z(·)`, with decisions:

```
declare  projected_boundary       iff  z(L) > 3 ∧ L > 0
                                       ∧ T_fail ≤ 1440 ∧ corroborated
declare  bounded_within_envelope  iff  z(U) < 3 ∧ z(L) > −3
declare  inconclusive_signal      otherwise.
```

### 10.2 Why interval endpoints, not the point estimate

Testing `z(L) > 3` (the lower endpoint) rather than `z(β̂) > 3` is the
confidence-interval/test duality applied conservatively: the harm
declaration requires that *every* slope value consistent with the data
at the interval's level lies outside the envelope. Symmetrically, the
safe declaration requires the *upper* endpoint inside. The two
declarations therefore cannot both hold (for 3 > −3), and the
indifference region maps to `continue`/`inconclusive` — the decision
function is well-defined.

### 10.3 The remaining conjuncts

- `L > 0`: restricts the harm declaration to positive drift; a large
  |z| attained by a *negative* slope (possible under a degenerate
  profile) must not trigger a growth alarm.
- `T_fail ≤ 1440` (Equation A6 with `q = 1` min⁻¹, levels 1000/500):
  bounds the declaration to breaches within the policy horizon;
  relevance filtering, not inference.
- *Corroboration*: for templates with auxiliary metrics, every
  auxiliary slope must be positive when declaring harm — a
  cross-metric sign consistency check that suppresses single-channel
  artifacts.
- *Post-deploy restriction*: only samples with `t ≥ deployed_at`
  enter the fit. Pre-deploy samples are draws from the stable process;
  including them biases `β̂` toward a mixture slope. For a window with
  fraction `ρ` of pre-deploy samples and true candidate slope `β_c`,
  the mixture fit approaches `(1−ρ)β_c` — for `ρ = 2/3` the estimate
  is attenuated threefold, sufficient to cross below the alarm
  threshold. The filter removes the bias at the cost of `n`.

### 10.4 Expressiveness bound

**Proposition 10.1.** The signal decision function's range excludes
`temporal_counterexample`.

*Proof.* A counterexample requires a replayable event sequence
(Definition 15.2 requires a drive log); signal mode executes no drive.
The strongest signal outcome is the extrapolation claim
`projected_boundary`. ∎

This bound is intentional and measured: the `clock_expiry` hazard
class carries no signal experiment (its failure has no pre-event
telemetry signature — the divergence functional is supported entirely
on post-event states), so the signal-only configuration provably
cannot detect it (§17.2).

---

## 11. Probe protocols and their decision functionals

A probe executes against an isolated instance whose behavior is a
deterministic function of `(seed, spec)` (§15). Probe calls are gated
by remaining wall-budget and deadline; mutating calls are appended to
an action log `σ = (op₁, …, op_n)` (the replay program). External
effects are structurally contained; the containment observation
`side_effect_attempts` enters the fidelity vector (§13).

### 11.1 `resource_lifecycle_v1` (playbooks/leak.py)

Model: `R(n) = R₀ + βn + ε_n` in lifecycle count `n`, `ε` heavy-tailed.

Protocol:

1. Execute `W = 100` warm-up cycles; set `R_warm = R(W)`. Warm-up
   samples are excluded: pool fill is a transient of the *correct*
   process, so including it biases `β̂` upward by the transient's
   secant slope.
2. Fix thresholds from policy and spec (pre-registered, Remark 2.3):

   ```
   τ_harm = (R_max − R_warm) / (T_horizon · q)     [handles/cycle]
   τ_safe = τ_harm / 4
   ```

   with `R_max = 1000`, `T_horizon = 1440 min`, `q = 60 cycle/min`:
   `τ_harm` is by construction the minimal slope whose extrapolation
   (A6) crosses `R_max` within the horizon; the factor 4 defines the
   indifference zone of §12.3.
3. For rounds `r = 1..8`: drive 100 cycles; record cumulative point
   `(n_r, R(n_r))` and round rate `δ_r = ΔR/100`; compute
   `z_r = z(δ_r)` against the reference (§9); the first `r` with
   `z_r > 3` fixes the divergence index and `a*` (Definition 2.2).
4. From `r ≥ 4`: fit `[L, U]` (Definition 6.3) on the cumulative
   points; call `decide(L, U, τ_harm, τ_safe, …)` (§12); stop on any
   non-`continue`.
5. On `fail`: construct the counterexample (Definition 15.2) and
   report `T_fail` per (A6).

### 11.2 `rate_balance_v1` (playbooks/retry.py)

Protocol: set dependency failure rate to `0.2`; drive rounds of 100
requests at concurrency 8; observe `m̂` = (retries)/(failures) and the
queue-depth series.

Decision functional:

```
FAIL  iff  m̂ ≥ 1  ∧  L(β̂_Q) > 0
SAFE  iff  U(β̂_Q) < 0.05  [per request]
```

The conjunction implements the theory of §§7–8 jointly: `m̂ ≥ 1` is
the supercriticality condition of Corollary 7.3 (necessary for
self-amplification), and `L(β̂_Q) > 0` is the observed fluid-drift
condition `λ > μ` of §8.1 (necessary for accumulation). Either alone
is insufficient: subcritical retries cannot amplify regardless of
transient queue growth, and a supercritical branching ratio with
`λ < μ` drains. Both conjuncts use conservative interval endpoints in
the sense of §10.2.

### 11.3 `cred_lifecycle_v1` (playbooks/credential.py)

The divergence functional is a counting functional with exact zero
tolerance; no statistical machinery is required or used.

Drive sequence (fixed):

```
cycle(50); requests(20×4)                    — precondition check:
                                                zero auth failures required,
                                                else abort inconclusive
advance(cred_age_s, TTL + 60); rotate_key(); refresh_fault(transient)
requests(20×4); requests(20×4)               — fault and recovery windows
```

Decision:

```
counterexample  iff  stale_reuse_count > 0
```

Correctness of the oracle: the specification of a correct client under
{expiry ∧ rotation ∧ one transient refresh failure} is
re-authentication with at most one bounded transient failure and
`stale_reuse_count = 0`. The set `{stale_reuse_count > 0}` is
therefore disjoint from every correct execution — the test has zero
false-positive probability *with respect to the specification*, and
`a*` is the age snapshot of the first counting event. The precondition
check (step 2) makes the test conditionally valid: a rig in which
baseline authentication already fails cannot attribute later failures
to the mechanism under test, and aborts as `inconclusive`.

---

## 12. The sequential stopping rule

(`rollout_fastforward/stopping.py`.) Inputs: interval `[L, U]`,
thresholds `τ_safe < τ_harm`, predicates `coverage_ok`, `fidelity_ok`,
and `budget_left ∈ ℝ`.

```
decide(L, U, τ_harm, τ_safe, coverage_ok, fidelity_ok, budget_left):
    1.  if L > τ_harm:                                  return fail
    2.  if budget_left ≤ 0:                             return inconclusive_budget
    3.  if U < τ_safe ∧ coverage_ok ∧ fidelity_ok:      return pass
    4.  else:                                           return continue
```

### 12.1 Basic properties

**Proposition 12.1.** For all inputs:
(i) the function is total and single-valued (first matching rule);
(ii) `pass` is returned only if `budget_left > 0 ∧ coverage_ok ∧
fidelity_ok ∧ U < τ_safe`;
(iii) `fail` and `pass` are mutually exclusive whenever
`τ_safe ≤ τ_harm` (since `L ≤ U` would otherwise give
`τ_harm < L ≤ U < τ_safe`, contradicting the ordering);
(iv) if `budget_left ≤ 0`, the range of the function is
`{fail, inconclusive_budget}`.

*Proof.* (i) The four guards are evaluated in a fixed order and rule
4 is unconditional. (ii) Rule 3 is reachable only when rules 1–2 do
not fire, giving the stated conjunction. (iii) Direct from `L ≤ U`
and `τ_safe ≤ τ_harm`. (iv) Rules 3–4 are unreachable once rule 2's
guard holds and rule 1's does not. ∎

Property (iv) is the formal statement of *"budget exhaustion is never
evidence of safety."* It is additionally verified by a randomized
test: 500 seeded bound-streams truncated at arbitrary budget points,
asserting the returned label is never `pass`.

**Remark 12.2 (asymmetry of rules 1 and 2).** Rule 1 precedes rule 2:
a confirmed exceedance (`L > τ_harm`) is reported as `fail` even at
zero budget. The decision-theoretic justification: at the moment the
interval clears the harm threshold, the datum is already sufficient
under the declared rule; budget accounting affects the *ability to
continue collecting*, not the validity of evidence already collected.

### 12.2 Duality with equivalence testing

**Proposition 12.3 (TOST duality).** Let `CI_{1−2α}` be a two-sided
`1−2α` confidence interval for an effect `Δ`. The decision rule
"declare equivalence iff `CI_{1−2α} ⊂ (−δ, δ)`" is equivalent to
rejecting both one-sided hypotheses `H₋ : Δ ≤ −δ` and
`H₊ : Δ ≥ δ` at level `α` each (Schuirmann's two one-sided tests),
and controls the type-I error of a false equivalence claim at `α`.

*Proof sketch.* `CI ⊂ (−δ, δ)` holds iff the upper endpoint is
below `δ` and the lower endpoint above `−δ`; each endpoint condition
is precisely the rejection region of the corresponding one-sided
`α`-level test by CI–test duality. Type-I control follows from the
intersection–union principle: under either boundary null, the
probability that its one-sided test rejects is ≤ α. ∎

Rule 3 (`U < τ_safe`) is the one-sided instance of this duality: a
passing claim is an *equivalence-style* claim requiring the entire
interval inside the tolerance region — the absence of a demonstrated
effect (`L < τ_harm` failing to trigger rule 1) is never itself
grounds for `pass`.

### 12.3 The indifference zone

The band `(τ_safe, τ_harm)` with ratio 4 is an indifference zone in
the sense of §10.1: intervals lying inside it produce `continue`
until budget exhaustion. Widening the ratio trades expected sample
size against the probability of terminating `inconclusive_budget` on
borderline effects; the ratio is a policy constant, not a fitted
parameter.

---

## 13. Fidelity aggregation

(`rollout_fastforward/fidelity.py`.) Fidelity quantifies the
resemblance of the experiment to production on six axes,
`f = (f_1, …, f_6) ∈ [0,1]⁶`:
input_shape, concurrency, clock_coverage, state_representativeness,
dependency_behavior, side_effect_semantics.

### 13.1 The aggregate

**Definition 13.1 (weighted geometric mean).** For weights
`w_k ≥ 0`, `Σ w_k = 1`:

```
F(f) = Π_k f_k^{w_k}  =  exp( Σ_k w_k ln f_k )                    (A13)
```

(the exponential–logarithmic form is the definition extended by
continuity with `F = 0` whenever some `f_k = 0` with `w_k > 0`).

**Proposition 13.2 (properties).**
(i) *Annihilation:* `F(f) = 0 ⇔ ∃k : w_k > 0 ∧ f_k = 0`
(since `ln f_k → −∞`).
(ii) *Monotonicity:* `F` is nondecreasing in each coordinate.
(iii) *Multiplicativity:* `F(f ⊙ g) = F(f) · F(g)` for coordinatewise
products — composing two lossy layers multiplies fidelities.
(iv) *AM–GM domination:* `F(f) ≤ Σ_k w_k f_k`, with equality iff all
`f_k` are equal; the geometric aggregate is never more optimistic
than the arithmetic one.

*Proof.* (i) and (ii) from properties of `ln`/`exp`. (iii) from
`ln(f_k g_k) = ln f_k + ln g_k`. (iv) is the weighted AM–GM
inequality (Jensen's inequality applied to the concave `ln`). ∎

**Justification of the functional form.** Interpret each `f_k` as the
probability that the mechanism under test survives layer `k` of the
simulation unchanged (that layer's abstraction does not destroy the
failure physics). Under independence of layers, the probability that
the mechanism survives *all* layers is the product — the geometric
form with exponents as calibrated importances. Property (i) then
states the correct semantics: one fully-unfaithful required layer
invalidates the composite evidence, regardless of the others.
Numerically: axes `(0.9, 0.9, 0.9, 0.6, 0.8, 1.0)` give arithmetic
mean 0.85, geometric 0.84; setting one axis to 0 gives arithmetic
0.68 but geometric 0 — only the latter matches the survival
semantics.

### 13.2 Structural cap

`state_representativeness` is clamped: `f_4 ← min(f_4, 0.6)`
(`SIM_STATE_CAP`) inside the report function. Rationale: the sim
probe target is specification-driven rather than state-cloned, so an
upper bound on this axis is a property of the instrument, not of any
particular run. Consequence: a hazard whose gate (below) requires
`f_4 > 0.6` cannot satisfy its gate on sim evidence — the bound is
enforced in the type of the report, not by convention.

### 13.3 Gates

**Definition 13.3.** Each hazard declares `req : axes ⇀ [0,1]`. The
gate predicate is

```
gates_met(f) ⇔ ∀ (k, m) ∈ req :  f_k ≥ m,
```

evaluated per axis, independently of `F`. The aggregate `F` is
reported for comparison; decisions consume `gates_met` (stopping rule
§12, lock 3; outcome rule 7, §14.1). This separation prevents
compensation: a high aggregate cannot mask a failed required axis,
because the gate is a conjunction of per-axis inequalities, not a
function of `F`.

---

## 14. Outcome derivation: a total precedence function

### 14.1 The outcome function

Let `ds` be the multiset of per-hazard dispositions,
`ds ⊆ {counterexample, within_envelope, projected_boundary,
inconclusive, unsupported, inconclusive_budget, …}` (open alphabet:
unknown labels may appear under partial upgrades), and `G` the
conjunction of all fidelity gates. Define
(`rollout_fastforward/results.py`):

```
O(ds, G) =
  temporal_counterexample        if counterexample ∈ ds            (1)
  inconclusive_budget            elif inconclusive_budget ∈ ds     (2)
  unsupported_temporal_risk      elif ∃ d ∈ ds :
                                   d ∉ {within_envelope,
                                        projected_boundary}        (3)
  no_material_temporal_hazard    elif ds = ∅                       (4)
  projected_boundary             elif projected_boundary ∈ ds      (5)
  bounded_future_envelope        elif G                            (6)
  projected_boundary             otherwise                         (7)
```

**Proposition 14.1 (totality and soundness).**
(i) `O` is total: rules 1–7 exhaust all `(ds, G)`.
(ii) Unknown dispositions map to `unsupported_temporal_risk`
(fail-toward-honesty).
(iii) The passing outcomes `{no_material_temporal_hazard,
bounded_future_envelope}` are reachable only when, respectively, no
hazards were compiled, or every disposition is `within_envelope` and
every fidelity gate holds.

*Proof.* (i) If rules 1–3 do not fire, then every element of `ds`
lies in `{within_envelope, projected_boundary}`. Rule 4 covers
`ds = ∅`; otherwise rule 5 covers the presence of
`projected_boundary`; the remaining case is `ds` nonempty and all
`within_envelope`, split exhaustively by `G` between rules 6 and 7.
(ii) An unknown label fails the membership test of rule 3's
complement set, so rule 3 captures it. (iii) By the guard structure:
rule 4 requires emptiness; rule 6 requires the rule-3 and rule-5
complements (all within envelope) and `G`. ∎

Rule 7 is the *fidelity demotion*: uniformly in-envelope measurements
taken by an instrument failing a required gate support only the
weaker extrapolation claim, not the equivalence claim
(cf. Proposition 12.3 — the equivalence claim requires the qualified
instrument that `fidelity_ok`/`G` encodes).

Failure handling: every exception in the execution worker is routed
through `degrade`, which finalizes with outcome
`unsupported_temporal_risk` *and mints a signed envelope stating the
reason*. Hence infrastructure failure is observationally equivalent
to "could not test" — never to "tested clean" — at every consumer.

### 14.2 The policy rule

The deterministic policy layer (`policies/rollout-slo.yaml@2`, rule
`temporal-evidence`, evaluated in `intel/rollout_intel/policy.py`
over verified envelopes only) is the map

```
temporal_counterexample                  ↦ fail
inconclusive_budget                      ↦ insufficient
unsupported_temporal_risk                ↦ insufficient
absent / unverifiable envelope           ↦ insufficient
no_material_temporal_hazard              ↦ pass
bounded_future_envelope                  ↦ pass
projected_boundary                       ↦ pass (advisory)
```

**Proposition 14.2 (defense in depth for non-passing outcomes).** The
invariant "`inconclusive_budget` never yields a pass" holds under
failure of either enforcement point.

*Proof.* The invariant is enforced independently at (a) the stopping
rule (Proposition 12.1(iv)) inside the Fast-Forward process, and (b)
the policy map above inside the rollout-intel process. A violation
would require both (a) to emit `pass` under exhausted budget and (b)
to map a non-passing outcome to `pass` — two independent negations in
distinct codebases. Under single-fault assumptions the invariant is
preserved. ∎

The reviewing agent operates strictly downstream of this map under
the *tighten-only* rule: the recorder rejects any verdict strictly
weaker than the policy status (`policy_conflict`), so agent
discretion is a one-sided lattice action (it may lower, never raise,
the health conclusion).

---

## 15. Determinism and replay

### 15.1 The determinism chain

**Proposition 15.1.** Every quantity produced by the pipeline —
hazard ids, plan, seeds, probe behavior, counterexample — is a pure
function of the canonical manifest `C(M)` and the fixture
specification.

*Proof.* By composition. (a) `d(M) = H₆₄(C(M))` is deterministic
(Proposition 3.2). (b) `hazard_id` is a function of `(class, traits,
d(M))` (Proposition 3.4); the signature table is constant. (c) The
plan is a function of the hazard set through a strict total order
(§5.2, step 1). (d) The seed is

```
seed(h) = int( H₆₄( d(M) ‖ hazard_id(h) )[:8 hex], 16 ) ∈ [0, 2³²),
```

a function of (a) and (b). (e) The probe target satisfies the
contract: identical `(seed, spec, call sequence)` ⇒ identical counter
and event trajectories (its internal randomness is drawn from a PRNG
seeded exclusively by `seed`; no wall-clock or OS entropy enters any
code path). (f) Playbook control flow depends only on (e)'s outputs
and pre-registered thresholds. Composition of deterministic functions
is deterministic. ∎

Empirical confirmation: two end-to-end executions from a reset world
(seed 42) produced identical hazard id, divergence age, event-digest,
and counterexample id (`cx_a0d5981cfe46`).

### 15.2 The counterexample artifact

**Definition 15.2.** A temporal counterexample is the tuple

```
( cx_id, candidate_digest, state_slice_digest,
  σ,                     — the mutations-only action log (drive program)
  expected_stable,       — reference statistics or specification
  observed_candidate,    — measured statistics, counters, event digest
  a*,                    — first-divergence age (Definition 2.2)
  seed )
```

with `cx_id = "cx_" ‖ H( d(M) ‖ hazard_id ‖ template )[:12]`. The
action log is minimal by construction in the MVP (playbooks emit only
mechanism-relevant operations); systematic minimization
(delta-debugging over `σ`, state, and interleavings) is roadmap.

### 15.3 Replay as verification

**Definition 15.3.** `replay(cx)` re-instantiates from
`(seed, spec)`, re-executes `σ`, and checks divergence recurrence at
the same `a*`.

By Proposition 15.1, for a correct artifact `replay` succeeds with
certainty; conversely a tampered `σ` or mismatched seed fails the
`a*` equality check. The system executes `replay` once before
reporting any counterexample (`replay_verified = 1`), making every
reported failure a *reproduced* failure by the time it reaches the
policy layer.

---

## 16. Evidence integrity: hash binding and HMAC

(`rollout_fastforward/envelope.py`, byte-compatible with
`mcp-servers/gcp/envelope.py`.)

### 16.1 Construction

For payload `p` and identity fields
`ι = (observation_id, type, scope, observed_at, fresh_until)`:

```
content_hash = SHA256( canonical(p) )
sig          = HMAC-SHA256( K, canonical( ι ∪ {content_hash} ) )
```

`K` is held by evidence-minting services and the verifier only; it is
never present in the agent sandbox or any prompt.

### 16.2 Security properties

**Proposition 16.1 (binding).** Assuming SHA-256 collision
resistance, an envelope's signature binds both identity and payload:
any modification of `p` changes `content_hash` (collision resistance)
and hence invalidates `sig`; any modification of `ι` invalidates
`sig` directly; a valid `sig` cannot be transplanted onto a different
payload because `content_hash ∈` the signed tuple. ∎

**Proposition 16.2 (unforgeability).** Under the standard assumption
that the SHA-256 compression function is a PRF, HMAC is existentially
unforgeable under chosen-message attack (Bellare, 2006). Hence a
party without `K` — in particular the reviewing agent — cannot
produce any envelope accepted by the verifier, except with negligible
probability. ∎

### 16.3 Verification semantics

The verifier checks (in order): signature equality
(constant-time comparison), payload-hash equality, and freshness
`now ≤ fresh_until`; the policy layer additionally checks scope
(`scope.service` must equal the episode's service). Failure of any
check places the envelope in `unverified_observations`, whose
elements satisfy **no** policy rule. Combined with §14.2's
absent-envelope row, verification failure is semantically identical
to absence: the attack surface reduces to denial (which yields
`insufficient`), never to forged health.

Freshness parameter: Fast-Forward envelopes set
`fresh_until = now + T_d + 86 400 s`, guaranteeing validity through
the decision checkpoint (a result minted at T+2 must verify at T+30)
plus an audit day, in contrast to the 600 s default of telemetry
envelopes.

---

## 17. Evaluation metrics and calibration

### 17.1 Definitions

Over a fleet with ground-truth labels (from the outcome collector,
never from agent verdicts):

```
recall            = |caught delayed regressions| / |seeded delayed regressions|
false-block rate  = |clean services blocked| / |clean services|
time-to-cx        = median( t_terminal − t_request )
reproducibility   = |counterexamples replaying identically| / |counterexamples|
```

Golden assertions (`scripts/ff-golden.sh`): recall = 3/3,
false-block = 0, all envelopes verified; reproducibility asserted by
`scripts/ff-replay.sh` via byte-equality of
`(hazard_id, template, event digest, a*)` across full resets.

### 17.2 The ablation experiment

`scripts/ff-arms.sh` compares arm C (`FF_MODE=signal_only`) with arm
D (full escalation). Predicted and observed: arm C detects the
resource leak (its divergence has a telemetry signature; §10) and
cannot detect the credential defect (Proposition 10.1 and the empty
signal-experiment set of `clock_expiry`); the miss is reported as
`unsupported_temporal_risk` ↦ `insufficient` — a *typed* miss, not a
false negative presented as health. Arm D detects 3/3. The measured
difference is the marginal detection value of the probe tier at its
marginal cost.

### 17.3 Calibration (roadmap)

Each episode stores `final_verdict` (reviewer), `final_label` (ground
truth) and the Fast-Forward outcome. The empirical frequencies

```
P̂(real | hazard class fired),   P̂(regression | counterexample),
P̂(healthy | bounded envelope)
```

are exactly the quantities required to fit (A2)'s posterior and the
detection powers `D(e,h)` of (A3), converting the constant relevance
weights of §4 into calibrated probabilities. The MVP accumulates the
joint distribution; the estimation step is deferred until label
volume supports it.

---

## Appendix A. Constants

| Constant | Value | Module | Role |
|---|---|---|---|
| `_MAD_K` | 1.4826 | stats.py | `1/Φ⁻¹(3/4)`; Derivation 6.8 |
| `_EPS` | 10⁻⁹ | stats.py | scale floor in Definition 6.9 |
| Interval percentiles | 0.05 / 0.95 | stats.py | §6.3 slope interval |
| Huber `k` | 1.5 | stats.py | Definition 6.11 (≈95 % normal efficiency) |
| Huber iterations | ≤ 20 | stats.py | IRLS cap, Derivation 6.12 |
| `Z_HARM` | 3.0 | signals.py | §10.1 threshold; Proposition 6.10 |
| `HORIZON_MIN` | 1440 | signals.py, probes.py | policy horizon (min) |
| `WINDOW_MINUTES` | 30 | signals.py | telemetry window |
| `MIN_POINTS` | 4 | signals.py, playbooks | minimum fit support |
| `LEVELS` | 1000 / 500 | signals.py | signal harm levels |
| `WARMUP_CYCLES` | 100 | leak.py | transient exclusion, §11.1 |
| `ROUND_CYCLES` × `MAX_ROUNDS` | 100 × 8 | leak.py | design grid |
| `PROD_CYCLES_PER_MIN` | 60 | leak.py | rate `q` in (A6) |
| `τ_safe : τ_harm` | 1 : 4 | leak.py | indifference zone, §12.3 |
| `Z_DIVERGE` | 3.0 | leak.py, retry.py | divergence index threshold |
| `FAILURE_RATE` | 0.2 | retry.py | dialed `p_f` |
| `SAFE_QUEUE_SLOPE` | 0.05/req | retry.py | §11.2 safe bound |
| `WARM_CYCLES`/`BATCH`/`CONC` | 50/20/4 | credential.py | §11.3 drive |
| `ADVANCE_SLACK_S` | 60 | credential.py | post-TTL margin |
| `SIM_STATE_CAP` | 0.6 | fidelity.py | §13.2 instrument bound |
| `SIGNAL_COST_S`/`PROBE_COST_S` | 5 / 30 (×2 no profile) | planner.py | §5.2 costs |
| Profile TTL | 14 d | profiles.py | §9.1 expiry |
| Envelope TTL | `T_d` + 86 400 s | results.py | §16.3 freshness |
| Relevance weights | .90/.85/.90/.60/.50/.50 | compiler.py | §4 floor |
| Budget (sim) | 6 steps / 60 s | relay.py | exogenous `B` |

## Appendix B. Statistical limitations, stated precisely

1. **Sequential examination of a fixed-sample interval.** The
   interval `[Q_{0.05}(S), Q_{0.95}(S)]` carries (at best)
   pointwise-in-time coverage; the stopping rule examines it at every
   round, i.e. at a data-dependent stopping time. For test statistics
   of random-walk type, the law of the iterated logarithm
   (`limsup_n |S_n| / √(2n log log n)` = 1 a.s.) implies any fixed
   ±c√n boundary is crossed infinitely often under the null, so
   naive repeated testing has asymptotic size 1. The correct
   instrument is a *time-uniform confidence sequence*: a family
   `(CI_t)` with `P( ∃ t : θ ∉ CI_t ) ≤ α`, constructed from
   nonnegative supermartingales via Ville's inequality
   (`P(sup_t M_t ≥ 1/α) ≤ α E[M₀]`; Howard et al., ref. R12).
   Present mitigations: a minimum-support rule (no decision before 4
   points), a wide indifference zone (factor 4), decision thresholds
   on interval *endpoints* rather than point estimates, and
   deterministic replay confirmation of every `fail`. The seam is
   interface-level: `decide(L, U, …)` is agnostic to the interval's
   construction; substituting a confidence-sequence producer modifies
   only `stats.py`.
2. **Uncalibrated priors.** The floor relevances are constants, not
   posterior probabilities; consequently plan ordering is only
   ordinal. Repair: fit (A2) on the accumulating labeled joint
   distribution (§17.3).
3. **Coverage aggregation.** The risk-weighted coverage functional
   `Coverage = Σ_h P(h|x) I_h c_h / Σ_h P(h|x) I_h` (A14) requires
   calibrated `P(h|x)`; the MVP reports per-hazard resolution status
   without aggregation, which is conservative (unresolved hazards are
   individually surfaced by §14.1 rule 3, not averaged).
4. **Point estimate of `m̂`.** The supercriticality test compares
   `m̂` to 1 without an interval. Near-critical cases are protected
   by the conjunction with the interval-based drift condition
   (§11.2); a binomial-ratio interval on `m̂` would complete the
   symmetry.
5. **Instrument bounds.** All fidelity ceilings (`SIM_STATE_CAP`,
   partial clock coverage) are properties of the sim instrument.
   Substituting a production probe target rebinds the axis scores;
   all statements in §§6–14 are instrument-independent and survive
   unchanged.
