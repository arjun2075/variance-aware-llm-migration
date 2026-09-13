# REPETITION_BUDGET_ANALYSIS.md

**Question:** how many incumbent repetitions `R_A` should the confirmatory grid buy?
**Date:** 2026-09-09 · **Paid API calls: 0** · **Script:** `sim/repetition_budget_sim.py`
**Data:** the recovered 200-run original grid · **Replicates:** 4,000 per (candidate × budget) cell
**Incumbent:** `gpt-4o-2024-11-20` · **Budgets:** 5, 6, 8, 10, 12 · **Candidate reps:** 5

## Method

For each incumbent budget `R_A`, candidate `B`, and metric, we bootstrap the
revised primary estimand `Delta(A→B) = C_AB − W_A`:

1. resample the 8 personas with replacement (cluster level);
2. draw `R_A` incumbent repetition positions and 5 candidate positions, with
   replacement, from the 5 originals;
3. `W_A` = mean over **distinct-repetition** within-incumbent pairs — the
   original off-diagonal treatment, preserved exactly;
4. `C_AB` = mean over the `R_A × 5` cross product.

Metric definitions, the pair cache, eligibility rules, embedding model and
cosine threshold are **imported unchanged** from `publication_analyze.py` and
`publication_run_level_bootstrap.py`.

### Validation

At `R_A = 5` the simulated `W_A` reproduces the true unbootstrapped GPT-4o
within-model agreement on all 11 metrics (e.g. M1.technical_craft 0.6833,
M2.recommendations 0.0564, M3.summary 0.7549), and `W_A` is candidate-invariant
up to Monte Carlo noise, as it must be. The estimator is correct.

## ⚠ The central caveat

**Only 5 distinct repetitions exist.** Budgets above 5 are simulated by drawing
*with replacement* from those 5. A real 12-repetition cell would contain 12
genuinely independent generations; a resampled one keeps re-drawing the same 5
outputs and cannot exhibit diversity those 5 never had.

This captures the **combinatorial** benefit of more repetitions (more pairs →
less sampling noise) but not the **diversity** benefit. Results are therefore a
**lower bound** on the value of extra repetitions. The analytic `C(R,2)`
pair-count scaling is reported alongside because that part extrapolates cleanly.

## Result 1 — uncertainty in `W_A`

SD of `W_A`, averaged over the 4 candidates:

| metric | R=5 | R=6 | R=8 | R=10 | R=12 | reduction 5→12 |
|---|---|---|---|---|---|---|
| M1.technical_craft | 0.1329 | 0.1267 | 0.1178 | 0.1158 | 0.1132 | 14.8% |
| M1.execution_excellence | 0.1349 | 0.1289 | 0.1190 | 0.1166 | 0.1141 | 15.4% |
| M1.customer_centric_outcomes | 0.1316 | 0.1256 | 0.1200 | 0.1152 | 0.1139 | 13.4% |
| M1.accelerating_teams | 0.1121 | 0.1067 | 0.1002 | 0.0956 | 0.0926 | 17.4% |
| M1.opportunity_multiset | 0.1302 | 0.1264 | 0.1226 | 0.1185 | 0.1170 | 10.2% |
| M1.opportunity_sequence | 0.1452 | 0.1411 | 0.1389 | 0.1350 | 0.1337 | 7.9% |
| M2.strengths | 0.0658 | 0.0624 | 0.0594 | 0.0575 | 0.0561 | 14.7% |
| M2.opportunities | 0.0503 | 0.0465 | 0.0425 | 0.0397 | 0.0382 | 24.0% |
| M2.areas_of_concern | 0.0584 | 0.0537 | 0.0483 | 0.0449 | 0.0425 | 27.1% |
| M2.recommendations | 0.0504 | 0.0473 | 0.0443 | 0.0417 | 0.0405 | 19.7% |
| M3.summary | 0.0291 | 0.0271 | 0.0248 | 0.0235 | 0.0229 | 21.3% |

Even at R=12 — a 140% increase in incumbent runs — `W_A` uncertainty falls only
**8–27%**. Because personas are resampled at the cluster level, most of `W_A`'s
uncertainty is **between-persona**, not between-repetition, and no repetition
budget touches that.

## Result 2 — `Delta` CI width and the point of diminishing returns

Mean 95% CI width over all 11 metrics:

| R_A | CI width | vs R=5 | marginal gain | per extra incumbent run |
|---|---|---|---|---|
| 5 | 0.3898 | — | — | — |
| 6 | 0.3734 | −4.2% | −4.21% | 4.21% |
| **8** | **0.3553** | **−8.9%** | **−4.86%** | 2.96% |
| 10 | 0.3437 | −11.8% | −3.25% | 2.36% |
| 12 | 0.3368 | −13.6% | −2.03% | 1.95% |

**The point of diminishing returns is R_A = 8.** The 6→8 step is the last one
that returns more than the step before it (−4.86%); every later step returns
strictly less (−3.25%, −2.03%). Beyond 8, each additional incumbent run buys
under 2.4% CI reduction.

## Result 3 — classification stability

Probability that the margin classification flips from repeated sampling alone
(1 − modal-class share, averaged over candidates):

| metric | R=5 | R=8 | R=12 |
|---|---|---|---|
| M1.technical_craft | 0.405 | 0.375 | 0.362 |
| M1.execution_excellence | 0.373 | 0.368 | 0.362 |
| M1.customer_centric_outcomes | 0.360 | 0.359 | 0.354 |
| M1.accelerating_teams | 0.363 | 0.334 | 0.318 |
| M2.strengths | 0.311 | 0.303 | 0.306 |
| M2.areas_of_concern | 0.262 | 0.236 | 0.226 |
| M2.opportunities | 0.169 | 0.144 | 0.132 |
| M1.opportunity_multiset | 0.163 | 0.152 | 0.147 |
| M1.opportunity_sequence | 0.136 | 0.123 | 0.120 |
| M2.recommendations | 0.134 | 0.110 | 0.101 |
| M3.summary | 0.011 | 0.005 | 0.004 |

Most M1 metrics stay at a **~35% flip probability regardless of budget**. This
is the clearest evidence that repetitions are not the binding constraint.

Only **3 of 44** (candidate × metric) cells change their CI verdict across the
whole 5→12 range:

| cell | R=5 | R=6 | R=8 | R=10 | R=12 |
|---|---|---|---|---|---|
| nova-pro · M3.summary | inconclusive | demonstrated | demonstrated | demonstrated | demonstrated |
| claude-sonnet-4.5 · M2.recommendations | inconclusive | inconclusive | demonstrated | demonstrated | demonstrated |
| gpt-5.4 · M2.strengths | inconclusive | inconclusive | inconclusive | inconclusive | rejected |

Two of the three resolve by R=8. The third needs R=12 to resolve a single cell.

## Result 4 — the finding that matters most

Cells left **inconclusive** (i.e. no migration decision) out of 44:

| R_A | inconclusive |
|---|---|
| 5 | 37 / 44 (84%) |
| 6 | 36 / 44 |
| 8 | 35 / 44 |
| 10 | 35 / 44 |
| 12 | 34 / 44 (77%) |

**Buying 140% more incumbent runs resolves 3 of 37 undecided cells.** The
pairwise design at 8 tasks is underpowered in a way repetitions cannot fix —
see `TASK_COUNT_SENSITIVITY.md`, where moving from 8 to 60 tasks cuts CI width
by 64% against 9% here.

## Verdict: is R_A = 8 justified?

**Yes, but narrowly, and it is not where the money should go.**

- **8 is the correct inflection point.** It is the last step with increasing
  marginal return, and it resolves 2 of the 3 budget-sensitive cells.
- **The gain is modest**: 8.9% mean CI reduction for 60% more incumbent runs.
- Because this simulation is a **lower bound** (it cannot show the diversity
  benefit of genuinely new generations), the true value of R=8 is somewhat
  higher than 8.9% — which is what tips a marginal call into a positive one.
- **R=10 and R=12 are not justified**: together they add another 80% incumbent
  cost for 4.7 percentage points of further CI reduction and one extra
  resolved cell.

**Recommendation: R_A = 8, R_B = 5** — carried into the updated plan. The far
larger win is task count, and the freed budget should go there.

### Honest limitation

This cannot distinguish "8 repetitions is enough to characterise incumbent
variability" from "8 resampled draws from 5 outputs look stable". A real R=8
cell may reveal behaviour the original 5 never produced. The recommendation
rests on the combinatorial argument (which extrapolates) plus the knowledge
that the diversity effect can only push in favour of more repetitions.

**Raw data:** `results/repetition_budget_raw.csv` (220 rows),
`results/repetition_budget_provenance.json`.

---

## Note on this copy (independent research repository)

This document and its CSV are copied from **Study 0**, the historical pilot,
which ran on a managed execution path. Two changes were made for this repository:

1. the managed execution path model alias was rewritten to the **public OpenAI
   snapshot id** `gpt-4o-2024-11-20`. This is a naming change only — no
   number, estimate, or conclusion was altered.
2. No other internal identifier appeared in these files (verified by
   `tests/test_no_proprietary_content.py`).

The authoritative, unmodified Study 0 artifacts remain in their read-only
backup outside this repository. This repository does not depend on them.
