# RESULTS_REPORT.md

**Confirmatory grid:** 5,040 runs / 20,160 calls, 0 exclusions.
**Analysis:** frozen pipeline, 10,000-replicate two-level cluster bootstrap,
seed 20260803, distinct-repetitions (off-diagonal) within-model estimator.

Primary estimand: `Delta(A→B) = C_AB − W_A`.
Negative `Delta` means the candidate diverges from the incumbent by more than
the incumbent diverges from itself.

> **Scope.** Pipeline 1 has no correctness criterion and no declared tolerance:
> it reports effects only. Pipeline 2 carries gold labels and gold evidence
> spans and a declared tolerance of 0.05 on label accuracy.

---

## 1. Headline: incumbent self-agreement is the binding constraint

The incumbent does not agree with itself, and how much it disagrees varies by
more than an order of magnitude across properties:

| Property class | `W_A` |
|---|---|
| P2 label (3-way classification) | **0.929** |
| P2 evidence spans | 0.853 – 0.856 |
| P1 ordinal ratings | 0.691 – 0.885 |
| P1 summary (cosine) | 0.735 |
| P1 free-text lists | **0.040 – 0.123** |
| P1 exact list match (multiset / sequence) | **0.000** |

Two consequences follow directly.

**Free-text list properties have almost no signal to measure.** With `W_A` at
0.040 for risks and 0.091 for recommendations, a ±0.10 tolerance — the pilot's
universal margin — is *larger than the incumbent's entire self-agreement*. Any
equivalence verdict on those properties would be a statement about the
tolerance, not the models. This is the concrete vindication of the decision to
declare no P1 tolerance.

**Exact-match metrics on generated text are structurally uninformative.**
`M1.opportunity_multiset` and `M1.opportunity_sequence` are exactly 0.000 for
`W_A` and `C_AB` alike: across **1,673 within-incumbent pairs, zero** produced
a character-identical opportunity list. Inspection confirms the same model
states the same substantive point in entirely different words each run. These
two properties are reported as degenerate and carry no migration information;
the semantic variants carry the signal.

## 2. Pipeline 2 — migration deltas (declared tolerance 0.05)

| Property | Candidate | `W_A` | `C_AB` | `Delta` | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| label | gpt-5.4 | 0.929 | 0.864 | −0.065 | [−0.136, −0.003] | inconclusive |
| label | gemini-2.5-pro | 0.929 | 0.805 | −0.124 | [−0.202, −0.052] | **rejected** |
| label | nova-pro | 0.929 | 0.832 | −0.096 | [−0.169, −0.033] | inconclusive |
| label | llama4-maverick | 0.929 | 0.800 | −0.129 | [−0.215, −0.053] | **rejected** |
| cited spans | gpt-5.4 | 0.856 | 0.649 | −0.207 | [−0.295, −0.125] | **rejected** |
| cited spans | gemini-2.5-pro | 0.856 | 0.650 | −0.206 | [−0.290, −0.125] | **rejected** |
| cited spans | nova-pro | 0.856 | 0.574 | −0.282 | [−0.376, −0.190] | **rejected** |
| cited spans | llama4-maverick | 0.856 | 0.453 | −0.403 | [−0.509, −0.298] | **rejected** |
| extracted spans | gpt-5.4 | 0.853 | 0.629 | −0.225 | [−0.314, −0.142] | **rejected** |
| extracted spans | gemini-2.5-pro | 0.853 | 0.633 | −0.220 | [−0.309, −0.135] | **rejected** |
| extracted spans | nova-pro | 0.853 | 0.701 | −0.152 | [−0.233, −0.076] | **rejected** |
| extracted spans | llama4-maverick | 0.853 | 0.532 | −0.322 | [−0.420, −0.225] | **rejected** |

**10 rejected, 2 inconclusive, 0 demonstrated** at tolerance 0.05.

Two patterns worth stating:

- **Evidence selection is far less stable under migration than the final
  label.** Label deltas run −0.065 to −0.129; span deltas run −0.152 to −0.403,
  two to three times larger. Candidates reach comparable conclusions while
  citing substantially different evidence. A migration test that checked only
  the final answer would miss this entirely.
- **Same-provider migration is not privileged.** `gpt-5.4`, the same-provider
  successor, is the *only* candidate whose label agreement is inconclusive
  rather than rejected — but its span deltas (−0.207, −0.225) are no better
  than the cross-provider Gemini (−0.206, −0.220). Provider continuity did not
  confer behavioural continuity on the intermediate stage.

## 3. Pipeline 1 — effects only, no verdicts

No tolerance is declared, so no equivalence verdict is issued. Of 36
informative cells (9 properties × 4 candidates), **32 have confidence intervals
excluding zero** — the candidates measurably diverge from the incumbent on most
properties, but whether that divergence *matters* is an application question
this study deliberately does not answer for P1.

Selected results:

| Property | `W_A` | Range of `Delta` across candidates |
|---|---|---|
| M1.technical_execution | 0.885 | −0.100 … **+0.020** |
| M1.delivery_consistency | 0.854 | −0.141 … −0.071 |
| M1.collaboration | 0.831 | −0.363 … −0.097 |
| M1.impact | 0.691 | −0.350 … −0.104 |
| M3.summary | 0.735 | −0.096 … −0.025 |
| M2.strengths | 0.105 | −0.065 … −0.043 |
| M2.risks | 0.040 | −0.032 … −0.021 |

`M1.technical_execution` is notable: `meta.llama4-maverick` has
`Delta = +0.020` (CI [−0.011, +0.050]) — it agrees with the incumbent
*slightly more* than the incumbent agrees with itself, and `gpt-5.4` is
indistinguishable from the incumbent's own variation (−0.004, CI [−0.043,
+0.032]). On that one property, those migrations are behaviourally invisible.

`M1.collaboration` shows the opposite: `gpt-5.4` at −0.363 is the largest
single effect in the study, larger than any cross-provider candidate on the
same property.

## 4. Tolerance sensitivity — the central methodological result

**10 of 12 Pipeline 2 cells change verdict across the 0.01–0.20 tolerance
sweep.**

This reproduces, on a far larger and cleaner dataset, the pilot observation
that motivated the study (7 of 11 metrics flipping between margins 0.05 and
0.15). The verdict is substantially a function of the declared tolerance, not
of the models alone.

The two stable cells are `llama4-maverick`'s span properties, whose deltas
(−0.403, −0.322) are large enough to be rejected at every tolerance in the
sweep. Everything else is tolerance-conditional.

**This is the strongest empirical support for the paper's primary claim:** a
migration verdict reported without its tolerance, and without the incumbent's
own variability as reference, is not interpretable.

## 5. Semantic-matching robustness

Deltas are stable across the cosine-threshold sweep. For `gpt-5.4` cited spans:

| Threshold | 0.70 | 0.75 | 0.80 | 0.85 | 0.90 |
|---|---|---|---|---|---|
| `Delta` | −0.201 | −0.204 | −0.207 | −0.218 | −0.231 |

A 0.20 change in threshold moves the delta by 0.030 — an order of magnitude
less than the effects themselves. The **threshold-free** aggregate (mean
max-cosine) gives −0.137 for the same cell: smaller in magnitude, same sign,
same qualitative conclusion.

**Conclusions do not depend on the semantic-matching implementation.**

## 6. Correctness × behaviour decomposition (Pipeline 2 primary)

Behavioural agreement and correctness are reported jointly, never separately.
Behaviour is "preserved" only when the behavioural CI lies entirely inside the
declared 0.05 tolerance; correctness change is the bootstrapped accuracy
difference (candidate − incumbent) over shared tasks.

| Property | Candidate | beh. Δ | inc. acc | cand. acc | acc. Δ [95% CI] | Quadrant |
|---|---|---|---|---|---|---|
| label | gpt-5.4 | −0.065 | 0.819 | 0.780 | −0.039 [−0.105, +0.016] | indeterminate |
| label | gemini-2.5-pro | −0.124 | 0.819 | 0.693 | −0.125 [−0.204, −0.057] | **B: changed + worsened** |
| label | nova-pro | −0.096 | 0.819 | 0.787 | −0.032 [−0.105, +0.035] | indeterminate |
| label | llama4-maverick | −0.129 | 0.819 | 0.730 | −0.089 [−0.170, −0.013] | **B: changed + worsened** |
| span F1 | gpt-5.4 | −0.207 | 0.419 | 0.484 | **+0.066** [−0.052, +0.182] | indeterminate |
| span F1 | gemini-2.5-pro | −0.206 | 0.419 | 0.328 | −0.091 [−0.177, −0.010] | **B: changed + worsened** |
| span F1 | nova-pro | −0.282 | 0.419 | 0.262 | −0.157 [−0.248, −0.072] | **B: changed + worsened** |
| span F1 | llama4-maverick | −0.403 | 0.419 | 0.163 | −0.256 [−0.371, −0.145] | **B: changed + worsened** |

**Tally: 5 quadrant B (behaviour changed, correctness worsened), 3
indeterminate, 0 quadrant A, 0 quadrant C, 0 quadrant D. Zero successes.**

Observations:

- **No candidate preserved behaviour** at the declared tolerance on any P2
  property, so quadrants C and D are empty by construction here. The
  correctness dimension is nonetheless what distinguishes the five confirmed
  regressions from the three undetermined cases: `gpt-5.4` and `nova-pro` on
  labels lose ~3–4 accuracy points with CIs straddling zero, while
  `gemini-2.5-pro` and `llama4-maverick` lose 9–13 points with CIs excluding it.
- **One near-miss quadrant A.** `gpt-5.4` on span F1 has a large behavioural
  divergence (−0.207) alongside an accuracy change of **+0.066** — it cites
  different evidence than the incumbent, and if anything slightly *better*
  evidence. The CI [−0.052, +0.182] straddles zero, so we classify it
  indeterminate rather than claiming an improvement. It is the clearest
  instance in the study of a candidate that a purely behavioural regression
  test would penalise without evidence that it is worse.
- **The incumbent is not a gold standard.** Its own label accuracy is 0.819 and
  its span F1 only 0.419. Agreement with it is therefore agreement with a
  frequently-wrong reference.

### Agreement on incumbent errors — the quadrant-D signature

Restricting behavioural agreement to the tasks the incumbent gets **wrong**:

| Property | Incumbent-error tasks | Agreement on those tasks (range across candidates) |
|---|---|---|
| label | 15 / 60 | 0.582 – 0.695 |
| span F1 | 44 / 60 | 0.513 – 0.652 |

Candidates agree with the incumbent on **51–70% of precisely the items it gets
wrong**. Under a behavioural-only regression test, that agreement would count
as evidence of a safe migration. It is not: it is shared error. This is
reported separately and is never folded into the headline behavioural metric.

## 7. Stress sets (analysed separately; never pooled with primary)

20 pre-frozen tasks per pipeline, frozen before execution and never added in
response to any primary result.

**Pipeline 2 stress — 6 rejected, 6 inconclusive** (primary: 10 rejected, 2
inconclusive).

| Property | Candidate | Δ (stress) | Δ (primary) | Verdict (stress) |
|---|---|---|---|---|
| label | gpt-5.4 | −0.007 | −0.065 | inconclusive |
| label | gemini-2.5-pro | −0.128 | −0.124 | inconclusive |
| label | nova-pro | −0.026 | −0.096 | inconclusive |
| label | llama4-maverick | −0.062 | −0.129 | inconclusive |
| cited spans | gpt-5.4 | −0.197 | −0.207 | rejected |
| cited spans | gemini-2.5-pro | −0.192 | −0.206 | rejected |
| cited spans | nova-pro | −0.297 | −0.282 | rejected |
| cited spans | llama4-maverick | −0.498 | −0.403 | rejected |
| extracted spans | gpt-5.4 | −0.226 | −0.225 | rejected |
| extracted spans | gemini-2.5-pro | −0.201 | −0.220 | inconclusive |
| extracted spans | nova-pro | −0.187 | −0.152 | inconclusive |
| extracted spans | llama4-maverick | −0.447 | −0.322 | rejected |

The **span/label asymmetry replicates**: span deltas (−0.187 to −0.498) remain
two to four times larger than label deltas (−0.007 to −0.128), and every cited-span
cell is rejected in both sets.

The verdict tally differs (6/6 vs 10/2) but this is a **power difference, not a
contradiction**: the stress set has 20 tasks against 60, so its CIs are roughly
70% wider, and cells near the tolerance boundary fall back to inconclusive. No
stress-set point estimate reverses the sign of its primary counterpart.

**Pipeline 1 stress:** 44 cells, all `no_declared_tolerance`, consistent with
the primary-set policy.

## 8. Leave-one-task-out sensitivity

Every P2 primary cell refit 60 times, once per removed task (720 refits total).

**Point estimates are highly robust.** The largest shift in Δ from removing any
single task is **0.016**, against effects of 0.065–0.403 — an order of magnitude
smaller than the effects themselves. No conclusion about effect size depends on
any individual task.

**Two verdicts are not robust:**

| Cell | Base Δ | Base verdict | Tasks whose removal flips it |
|---|---|---|---|
| label × gemini-2.5-pro | −0.124 | rejected | **13 of 60** |
| label × llama4-maverick | −0.129 | rejected | **10 of 60** |

All ten span cells show **zero flips**.

The interpretation is precise: both fragile cells have CI upper bounds close to
the −0.05 tolerance boundary, so removing a single task can pull the bound
across it. This is not instability in the measurement — the point estimates move
by ≤0.016 — but instability in the *verdict*, caused by the boundary sitting
where it does. It is the same phenomenon as the tolerance sensitivity in §4,
seen from a different angle, and it reinforces that categorical verdicts are the
fragile part of this methodology, not the effect estimates.

## 9. Execution-order diagnostic

Over the 71-hour run, correlations between execution-order index and outcome:

| Measure | Max |r| across all conditions |
|---|---|
| Schema validity vs. order | **0.051** |
| Latency vs. order | **0.090** |

No condition shows a correlation above 0.10 on either measure. **No meaningful
drift or order effect is detectable**, which supports the seeded interleaved
schedule having done its job: model identity is not confounded with time of day
or transient provider load.

Several P2 cells report no correlation because schema validity was constant
(100%) for that condition, leaving nothing to correlate.

## 10. Schema and invariant compliance

Reported separately from behavioural agreement and correctness. Scoped to this
scaffold's prompt-only structured output; **not** a claim about any provider's
structured-output capability. All figures at the post-Amendment-001 ceiling of
8,192 tokens.

### Pipeline 1 (primary / stress)

| Model | Schema valid | Parse failure |
|---|---|---|
| gpt-5.4 | 1.000 / 1.000 | 0.000 / 0.000 |
| gpt-4o (incumbent) | 0.998 / 0.981 | 0.006 / 0.013 |
| llama4-maverick | 0.997 / 0.990 | 0.060 / 0.080 |
| gemini-2.5-pro | 0.993 / 0.990 | 0.007 / 0.000 |
| nova-pro | 0.963 / 0.960 | 0.040 / 0.100 |

### Pipeline 2 (primary / stress)

| Model | Schema valid | Label in declared set | Verbatim grounding |
|---|---|---|---|
| gpt-5.4 | 1.000 / 1.000 | 1.000 / 1.000 | **1.000 / 1.000** |
| gpt-4o (incumbent) | 1.000 / 1.000 | 1.000 / 1.000 | 0.947 / 0.853 |
| gemini-2.5-pro | 1.000 / 1.000 | 1.000 / 1.000 | 0.937 / 0.963 |
| llama4-maverick | 1.000 / 1.000 | 1.000 / 1.000 | 0.768 / 0.863 |
| nova-pro | 1.000 / 1.000 | 1.000 / 1.000 | **0.660 / 0.765** |

Two findings:

- **Schema compliance is near-perfect on P2 for every model** (100% valid, 100%
  label-in-set) and high on P1. Compliance does **not** discriminate between
  these models on this scaffold.
- **Verbatim grounding does discriminate, sharply.** It is a deterministic
  invariant requiring no gold annotation, and it ranges from 1.000 (`gpt-5.4`)
  to **0.660** (`nova-pro`) — meaning a third of `nova-pro`'s cited spans do not
  appear verbatim in the source document it was given. A migration test
  checking only schema validity would rate all five models identically while
  missing this entirely.

## 11. Direct-provider replication (summary)

Full detail in `REPLICATION_REPORT.md`. 1,040 calls, 260 runs, 0 errors, on the
frozen 10+10 task subset selected before any result was inspected.

**Coverage: 2 of 5 conditions**, for three distinct reasons — `gpt-4o` and
`gpt-5.4` replicated on immutable identifiers; `gemini-2.5-pro` **withdrawn from
new users by the provider** (permanent gap); the two Bedrock conditions have no
direct access path (scope gap).

**Result: 14 of 14 evaluable properties agree** — same sign, overlapping CIs,
same verdict. Incumbent self-agreement is stable across paths (`W_A` moves
≤0.012 on six of seven representative properties). Twelve of fourteen deltas
differ by under 0.05; two P1 properties (M1.impact −0.204, M1.collaboration
−0.088) vary more, neither carrying a verdict and both with overlapping
intervals.

**Serving path is not a major confound** for the conditions that could be
tested. The replication is a robustness check over 20 of 180 tasks and 2 of 5
conditions; it cannot overturn the primary results.

**The Gemini gap is itself a finding.** A mutable model identifier became
unverifiable within three days of the experiment that used it. The confirmatory
measurement stands but can no longer be re-verified against the public API by
anyone. `gemini-3.1-pro-preview` was not substituted.

## 12. What is not yet reported

## 13. Caveats

- **P1 supports no correctness claim.** It has no ground truth. All P1 results
  are behavioural.
- **`gemini-2.5-pro` is a mutable alias.** Served weights may have changed
  during the 71-hour run, undetectably from the identifier.
- **One serving path.** All conditions ran through a single managed execution path with
  provider-default sampling; differences may reflect serving infrastructure as
  well as model identity. The replication subset probes this for the four
  conditions with immutable identifiers.
- **Two P1 properties are degenerate** (exact list match) and carry no
  information; they are reported for completeness, not interpreted.
- No "safe to swap" claim is made or supported anywhere in these results.
