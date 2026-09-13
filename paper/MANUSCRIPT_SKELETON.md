# Variance-Aware Regression Testing for Model Migration in Compound LLM Pipelines

**DRAFT SKELETON — results-independent sections only.**

Every numeric result in this document is a placeholder of the form `[R-n]`,
resolved from the analysis outputs after the confirmatory grid completes. No
placeholder has been filled, and no scientific result has been inspected at the
time of writing. Sections whose *content* depends on results carry a
`RESULTS-DEPENDENT` marker and are deliberately left as stubs.

---

## Abstract

`RESULTS-DEPENDENT` — stub. Structure:
1. Migration decisions are made against a deterministic regression-testing
   intuition that compound LLM pipelines do not satisfy.
2. We reframe migration as a stochastic regression-testing problem, with the
   incumbent's own run-to-run variation as the reference.
3. Two compound pipelines, five model conditions, [R-1] accepted runs.
4. Findings: `RESULTS-DEPENDENT`.
5. Implication: migration compatibility is a property of a pipeline, workload,
   output property, serving configuration and tolerance — not of two model names.

## 1. Introduction

Teams replace the model inside a deployed LLM pipeline routinely: a provider
deprecates a snapshot, a cheaper model appears, a successor promises better
reasoning. The question asked before the swap is almost always framed as a
regression test — *does the new model still do what the old one did?*

That framing imports an assumption from deterministic software: that the
incumbent has a fixed behaviour to regress against. It does not. Run the same
prompt through the same model twice and the outputs differ. In a compound
pipeline, where each call consumes the previous call's output, that variation
compounds.

So the comparison that matters is not *candidate versus incumbent*, but
**candidate-versus-incumbent relative to incumbent-versus-itself**. A candidate
that disagrees with the incumbent no more than the incumbent disagrees with
itself has not regressed in any sense a regression test can detect.

This paper makes that comparison the primary estimand and reports it per
pipeline, per output property, and per declared tolerance.

**Contributions.**
1. A variance-aware pairwise estimand `Delta(A→B) = C_AB − W_A` for model
   migration, with a cluster bootstrap over task instances and an off-diagonal
   treatment for the within-model baseline.
2. A decomposition that separates behavioural preservation from correctness,
   exposing the case a behavioural regression test gets backwards: a candidate
   that changes behaviour while improving correctness.
3. An empirical study over two structurally different compound pipelines,
   including one with independently checkable outputs.
4. Evidence on whether migration verdicts are stable across tolerance choices.

## 2. Motivating observation: the tolerance is doing the work

`RESULTS-DEPENDENT` in its numbers; the argument is not.

A pilot study of a four-call assessment pipeline over eight synthetic task
instances, five models and five repetitions (200 accepted runs) reported a
panel-level equivalence verdict against a universal ±0.10 margin. Re-examining
it, two properties of that result motivate this work:

- Of eleven metrics, **seven changed verdict** between margins 0.05 and 0.15.
  The headline was substantially a statement about the chosen tolerance.
- Incumbent self-agreement was as low as **0.052** on one content metric. A
  ±0.10 tolerance exceeded the entire available signal for that property.

The pilot is reproduced here as motivation only (§7.1); its data is never
pooled with the confirmatory grid.

## 3. Method

### 3.1 Estimand

For incumbent `A` and candidate `B` on property `p`:

```
Delta_p(A→B) = C_AB,p − W_A,p
```

`W_A,p` is the incumbent's self-agreement on `p`: the mean pairwise agreement
between **distinct** repetitions of `A` on the same task. `C_AB,p` is the mean
agreement over the full `R_A × R_B` cross product.

`Delta` near zero means the candidate is no more different from the incumbent
than the incumbent is from itself. Negative values mean the swap introduces
divergence beyond the incumbent's own variability.

### 3.2 The off-diagonal treatment

`W_A` must be formed over distinct repetitions. Comparing a repetition with
itself scores 1.0 by construction, and under a bootstrap that draws repetitions
with replacement such self-pairs appear at rate `1/R_A`, biasing `W_A` upward by
approximately `(1/R_A)(1 − W_A^true)` and pushing `Delta` spuriously negative.
The bias is largest exactly where `W_A` is smallest — the low-agreement content
properties where the question is most delicate.

The pilot data shows the consequence: under a self-inclusive estimator the
observed point estimate falls outside its own 95% interval for 6 of 11 metrics,
the diagnostic signature of a biased estimator. All results here use the
distinct-repetitions estimator; the self-inclusive variant is retained only as a
labelled diagnostic.

### 3.3 Uncertainty

Two-level cluster bootstrap, 10,000 replicates, seed 20260803: resample task
instances with replacement, then repetitions within each task × model cell.
Intervals are empirical 2.5/97.5 percentiles. Task instances are the clustering
unit because repetitions within a task are not independent.

### 3.4 Tolerances

A migration verdict is meaningless without a declared tolerance, and a universal
tolerance is not defensible across properties measured on different scales.

For Pipeline 2, tolerances are declared in advance where an application-grounded
justification exists: 0.05 for label accuracy, 0.01 for the verbatim-grounding
invariant, 0.05 for schema validity.

**For Pipeline 1 no tolerance is declared.** No application-grounded threshold
exists for its behavioural agreement metrics, so Pipeline 1 reports effect sizes
and tolerance-sensitivity curves and issues **no equivalence verdict**. This is a
deliberate methodological position, and a departure from the pilot's universal
±0.10.

All properties are additionally reported across a tolerance sweep
(0.01–0.20, nine points) with a classification-stability summary.

### 3.5 Correctness versus behaviour

For a pipeline with ground truth, behavioural agreement and correctness are
distinct and can move in opposite directions. Four outcomes:

| | correctness improved | correctness degraded |
|---|---|---|
| **behaviour changed** | **A** — candidate is better; a behavioural regression test *fails* it | **B** — genuine regression |
| **behaviour preserved** | **C** — low-risk migration | **D** — incumbent's error preserved |

Quadrant **A** is the case the deterministic intuition inverts. Quadrant **D** is
the one it cannot see at all: outputs agree, and they agree on being wrong.

We therefore report the joint cell for every (candidate, property) and never
report behavioural preservation for Pipeline 2 without the paired correctness
change. We additionally pre-register the subset of instances the incumbent gets
**wrong**, and report behavioural agreement on that subset separately — high
agreement there is the quantitative signature of quadrant D.

## 4. Experimental design

### 4.1 Pipelines

**Pipeline 1 — evaluative assessment.** Four sequential calls:
contribution signal → collaboration signal → synthesis → deepen. Each stage
consumes the previous stage's output. Outputs are structured ratings, lists and
free text with **no ground truth**; Pipeline 1 therefore supports behavioural
claims only. Prompts were newly authored for this study and are released in
full (Appendix A).

**Pipeline 2 — contract clause NLI.** Four sequential calls: evidence
extraction → evidence assessment → structured classification → verification.
Built on ContractNLI (CC BY 4.0), which supplies gold three-way labels **and**
gold evidence spans, giving both an objective final-answer criterion and an
objective intermediate criterion. Prompts newly authored and released.

The pipelines differ in input modality (structured records vs. multi-page legal
prose), output type (open-ended assessment vs. constrained classification), and
critically in whether correctness is checkable at all.

### 4.2 Task instances

60 primary instances per pipeline, plus **20 stress instances per pipeline
frozen in advance, analysed and reported separately**. The stress sets are never
merged into the primary sample and were never added in response to a primary
result.

Pipeline 1 instances are synthetic, generated across six independent axes
(seniority, work archetype, difficulty, ambiguity, evidence volume, evidence
conflict mode) with an enforced distinct-signature constraint, so the corpus is
not a paraphrase family. No real personnel data is used; a validator enforces
the absence of identifiers.

Pipeline 2 instances are sampled at the **document** level — ContractNLI pairs
each document with the same 17 hypotheses, so document × hypothesis pairs are
not independent and sampling them would understate cluster uncertainty. Labels
are balanced 20/20/20 in the primary set.

Gold labels and gold spans are used **only** for post-hoc scoring; a redaction
step strips them before prompt rendering, asserted by test and re-verified
against every rendered prompt.

### 4.3 Design parameters

| Parameter | Value |
|---|---|
| Primary task instances | 60 per pipeline |
| Stress instances | 20 per pipeline, separate |
| Incumbent repetitions | 8 |
| Candidate repetitions | 5 |
| Candidates | 4 |
| Stages per run | 4 |
| Planned runs / calls | 5,040 / 20,160 |

**Repetition budget.** Incumbent repetitions were set by simulation on the pilot
data rather than assumed. Across budgets {5, 6, 8, 10, 12}, mean interval width
fell 4.2%, 8.9%, 11.8% and 13.6% relative to five; the 6→8 step was the last
whose marginal return exceeded the preceding step. Eight was selected as the
point of diminishing returns. The same simulation showed repetitions to be the
weaker lever: at five repetitions 37 of 44 (candidate × property) cells were
inconclusive, and at twelve still 34 of 44.

**Task count.** The same approach over {8, 20, 40, 60, 80, 100} instances gave
interval-width ratios tracking the analytic `1/√T` closely (0.363 observed vs.
0.365 predicted at T=60). Moving from 8 to 60 instances reduced width 63.7%,
against 8.9% for the 5→8 repetition step — roughly sevenfold more effective per
unit of the design. Sixty was selected at the knee. We note this extrapolates
from eight distinct pilot instances and is not a power calculation.

### 4.4 Model conditions

`RESULTS-DEPENDENT` for observed behaviour; the matrix is fixed.

One incumbent and four candidates spanning four provider families, executed
against a single serving path. Four conditions carry immutable versioned
identifiers; one is a mutable alias, recorded as a reproducibility limitation
(§7.3).

The execution path rewrote three of five requested identifiers (a vendor suffix is
dropped; two gain a regional prefix). A requested→canonical map was established
by live probe before execution, and every call's returned canonical identifier is
checked against it. A mismatch flags the run rather than being silently accepted.

### 4.5 Execution

Execution order is a seeded permutation over (task × model × repetition), so
conditions are interleaved rather than run model-major; this avoids confounding
model identity with time-of-day and transient provider load. An execution-order
index and wall-clock timestamp are recorded per call, supporting a
pre-registered order-effect diagnostic.

the managed execution path does not permit concurrent requests, so execution is serial with a
minimum inter-call interval (2 s general, 15 s for Bedrock-backed families).
These intervals were conservative defaults rather than measured limits; §7.4
reports what was actually observed.

Recorded per call: pipeline, task, requested and canonical model, repetition,
stage, timestamps, latency, retries, token usage, parse outcome, schema outcome
and request configuration.

### 4.6 Acceptance, retry and exclusion

Frozen before execution. A run is **accepted** when all four stages return and
the record validates. **Schema violations and parse failures are data, not
exclusion criteria** — they are reported compliance metrics, and excluding them
would bias exactly the quantity being measured.

Exclusion is limited to: transport failure after the retry budget is exhausted,
canonical model mismatch, and prompt-context hash mismatch. No run is excluded
after its metric values are known.

Per-metric eligibility is explicit: a pair is ineligible when either side lacks
the field, and ineligible pairs are excluded rather than scored zero. Eligible
pair counts therefore vary by property and are reported.

## 5. Metrics

### 5.1 Pipeline 1 — behavioural

Ordinal agreement on four rating dimensions (normalised ordinal distance, with
an explicit `insufficient_data` category treated as nominal); exact multiset and
exact ordered-sequence agreement on generated opportunity lists; semantic
set-overlap on four free-text list fields; cosine similarity on the summary.

### 5.2 Pipeline 2 — six separated axes

1. incumbent self-variation `W_A`
2. incumbent→candidate behavioural agreement `Delta`
3. evidence-span correctness against gold spans (precision / recall / F1)
4. label correctness against gold labels (accuracy, per-class F1)
5. structured-output invariants: schema validity, parse success,
   label-in-declared-set, and **verbatim span grounding** — every cited span must
   appear as an exact substring of the source after whitespace normalisation, a
   deterministic check requiring no annotation
6. operational: latency, tokens, retries

### 5.3 Semantic-matching robustness

Semantic list metrics use `all-mpnet-base-v2` at a pinned revision with cosine
threshold 0.80 and one-to-one greedy matching. Because a thresholded metric can
encode its threshold into the conclusion, we additionally report the threshold
swept over {0.70, 0.75, 0.80, 0.85, 0.90} and a **threshold-free** aggregate
(mean of row- and column-wise maximum cosine). The purpose is to establish
whether qualitative conclusions depend on the matching implementation, not to
select a favourable configuration; all variants are reported.

## 6. Results

`RESULTS-DEPENDENT` — all stubs. See §9 for the planned figures and tables.

- 6.1 Execution and data quality — [R-1] accepted runs, [R-2] exclusions
- 6.2 Incumbent self-variation `W_A` by pipeline and property
- 6.3 Migration deltas with intervals
- 6.4 Correctness × behaviour decomposition (Pipeline 2)
- 6.5 Tolerance sensitivity and classification stability
- 6.6 Stress-set results, reported separately
- 6.7 Cross-pipeline comparison
- 6.8 Operational profile
- 6.9 Direct-provider replication subset

## 7. Reproducibility and limitations

### 7.1 Relationship to the pilot study
Reproduced as motivation; never pooled with confirmatory data. Reproduction
status: 21 of 23 recoverable results exact, 3 with float-level rounding
differences, 0 disagreements.

### 7.2 Amendment 001 — output ceiling
An initial 82-call quality-control run exposed a uniform output-token ceiling
(2,048) that truncated one condition on 15 of 28 calls (54%) while no other
condition truncated once. That condition expends most of its completion budget
on internal reasoning tokens (~0.13 characters of visible output per completion
token, against ~4.5 for the incumbent), so the ceiling curtailed its visible
answer rather than its reasoning. Left in place it would have assigned that
candidate a schema-violation rate that was an artifact of the output budget
rather than a property of the model.

The ceiling was raised **uniformly to 8,192** for all five conditions; per-model
ceilings were rejected because they would make the serving configuration
non-uniform across the comparison. The QC run was quarantined with a recorded
hash and excluded from all analysis, and the confirmatory experiment restarted
from zero. Post-amendment verification on previously-used task/model
combinations: truncation 15/28 → 0/7, other conditions 0, all outputs parseable,
all provenance correct.

The amendment was discovered during execution QC rather than outcome analysis,
applied uniformly, documented before the restart, and accompanied by no change
to tasks, prompts, model identities, repetition counts, estimands, tolerances,
retry rules or randomization.

### 7.3 Mutable model identifier
One condition is a mutable alias on both the managed execution path and the public API; the
managed execution path returns the alias unresolved. Served weights may therefore change within
or between runs, undetectably from the identifier. Divergences involving that
condition cannot be attributed to serving path versus weight change. The other
four conditions carry immutable identifiers.

### 7.4 Execution pacing
`RESULTS-DEPENDENT` for the final count. The serial schedule and per-family
intervals were conservative defaults, not measured limits; the observed rate of
throttling responses is reported so replicators need not inherit the same
conservatism.

### 7.5 Serving configuration
All confirmatory conditions ran as-operated through one managed execution path, with
provider-default sampling and an explicit token ceiling. Observed differences
may reflect serving infrastructure as well as model identity; the replication
(§6.9) probes this for the four conditions with immutable identifiers.

### 7.6 Terminology
We use *behavioural preservation*, *migration compatibility* and
*property-specific equivalence*. We do not claim any swap is "safe": Pipeline 2's
correctness criterion licenses correctness claims for Pipeline 2 properties
only, and Pipeline 1 has no correctness criterion at all.

## 8. Related work
Stub. Threads: LLM output variability and self-consistency; equivalence testing
and TOST; compound/agentic pipeline evaluation; regression testing for
non-deterministic systems; LLM-as-judge reliability.

## 9. Planned figures and tables
See `paper/FIGURES_AND_TABLES.md`.

## Appendix A — prompts
All eight prompt templates, verbatim.

## Appendix B — reproducibility artifacts
Protocol, hashes, corpus manifests, environment lock, container spec.
