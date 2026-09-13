# TASK_COUNT_SENSITIVITY.md

**Question:** how many distinct task instances per pipeline — 40, 60, 80, 100?
**Date:** 2026-09-09 · **Paid API calls: 0** · **Script:** `sim/task_count_sim.py`
**Data:** the recovered 200-run original grid · **Replicates:** 3,000 per task count

## ⚠ Read this first — the extrapolation is approximate

**The original study contains only 8 distinct profiles.** Drawing 100 cluster
slots from those 8 reduces cluster-*sampling* noise around this specific
8-persona population; it **cannot** introduce workload diversity the 8 never
contained.

A real 60–100 task workload — deliberately varied in difficulty, ambiguity,
input length, and evidence conflict, as Stage 6A requires — would almost
certainly be **more heterogeneous** than these 8 (built as 4 seniority levels ×
4 archetypes). Higher between-cluster variance would widen the CIs.

Therefore:
- the **shape** of the curve (1/√T) is trustworthy and is what the recommendation rests on;
- the **absolute CI widths at T > 8 are optimistic** — treat them as a floor;
- **this is not a power calculation** and must not be reported as one.

It answers *"where does adding tasks stop paying for itself?"*, not *"what CI
will I get at T = 60?"*

## Method

The hierarchical bootstrap already resamples personas as the top-level cluster.
We hold the estimated between-persona variance fixed at what the 8 personas
exhibit and vary only the number of clusters drawn per replicate, reusing the
unmodified pair cache, metric definitions, and off-diagonal within-model
treatment.

## Result — CI width by task count

Panel-level `Delta` 95% CI width:

| metric | T=8 | T=20 | T=40 | T=60 | T=80 | T=100 |
|---|---|---|---|---|---|---|
| M1.technical_craft | 0.2653 | 0.1735 | 0.1180 | 0.0964 | 0.0847 | 0.0759 |
| M1.execution_excellence | 0.2450 | 0.1544 | 0.1108 | 0.0914 | 0.0778 | 0.0695 |
| M1.customer_centric_outcomes | 0.2054 | 0.1305 | 0.0934 | 0.0751 | 0.0652 | 0.0593 |
| M1.accelerating_teams | 0.2277 | 0.1417 | 0.1000 | 0.0833 | 0.0711 | 0.0650 |
| M1.opportunity_multiset | 0.1806 | 0.1143 | 0.0814 | 0.0641 | 0.0575 | 0.0514 |
| M1.opportunity_sequence | 0.2042 | 0.1239 | 0.0902 | 0.0725 | 0.0641 | 0.0588 |
| M2.strengths | 0.1002 | 0.0636 | 0.0448 | 0.0359 | 0.0327 | 0.0279 |
| M2.opportunities | 0.0881 | 0.0547 | 0.0396 | 0.0316 | 0.0278 | 0.0249 |
| M2.areas_of_concern | 0.1829 | 0.1128 | 0.0791 | 0.0667 | 0.0561 | 0.0499 |
| M2.recommendations | 0.0518 | 0.0326 | 0.0237 | 0.0193 | 0.0168 | 0.0148 |
| M3.summary | 0.0447 | 0.0286 | 0.0200 | 0.0165 | 0.0143 | 0.0131 |

### Mean over metrics, with marginal gain

| tasks | CI width | vs T=8 | marginal gain | analytic 1/√T |
|---|---|---|---|---|
| 8 | 0.1633 | 1.000 | — | 1.000 |
| 20 | 0.1028 | 0.629 | −37.1% | 0.632 |
| 40 | 0.0728 | 0.446 | −29.1% | 0.447 |
| **60** | **0.0593** | **0.363** | **−18.5%** | **0.365** |
| 80 | 0.0517 | 0.316 | −13.0% | 0.316 |
| 100 | 0.0464 | 0.284 | −10.1% | 0.283 |

**The empirical curve tracks the analytic 1/√T almost exactly** (0.363 vs 0.365
at T=60; 0.284 vs 0.283 at T=100). The cluster bootstrap is behaving as theory
predicts, which is the main reason to trust the curve's shape even though the
absolute widths are optimistic.

## Task count vastly outperforms repetition count

| lever | change | mean CI reduction |
|---|---|---|
| incumbent repetitions | 5 → 8 | **8.9%** |
| incumbent repetitions | 5 → 12 | 13.6% |
| **task instances** | **8 → 60** | **63.7%** |
| task instances | 8 → 100 | 71.6% |

Going from 8 to 60 tasks is **seven times** more effective than going from 5 to
8 repetitions. Every marginal dollar should buy tasks before it buys
repetitions.

## Caveat on verdict resolution

Resolved (non-inconclusive) panel metrics stay at 7/11 from T=20 to T=100. This
is *not* evidence that tasks don't help — it is an artifact of the extrapolation:
because between-persona variance is frozen at the 8-persona estimate, the point
estimates never move, so metrics whose `Delta` sits far from the margin stay
resolved and those sitting near it stay ambiguous. **Treat CI width, not verdict
counts, as this analysis's output.** Real added tasks would move point estimates
too.

## Recommendation

**60 tasks per pipeline, with 75–80 preferred if authoring capacity allows.**

- **40 is too few.** The 40→60 step still returns 18.5%, the largest remaining
  marginal gain.
- **60 is the knee.** It captures 64% of the achievable CI reduction; the next
  step (60→80) returns 13.0% and the one after that 10.1%.
- **80 is a genuine improvement** (−13.0%) and worth taking if the tasks can be
  made *genuinely* heterogeneous. The cost analysis shows 80 tasks is
  affordable.
- **100 is not worth it** on these numbers: +10.1% CI reduction for +25% cost
  over 80, and a much larger authoring burden that raises the risk of the
  template-variation failure mode.

This matches your stated preference: 60 genuinely heterogeneous tasks beat 100
weak variations. Since real heterogeneity will widen CIs relative to this
optimistic simulation, **build for 60, and spend any surplus effort on
diversity rather than count**.

**Raw data:** `results/task_count_sensitivity.csv`, `results/task_count_provenance.json`.
