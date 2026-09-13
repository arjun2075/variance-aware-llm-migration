# Evaluation-budget study

- real 60-task PRIMARY P2 data only (stress excluded)
- deterministic subsamples per cell: **40** (seed `20260803`)
- bootstrap replicates: 300
- reference cell: T=60, R_A=8, R_B=5

## 1. Precision gained by adding TASKS (repetitions fixed at 8/5)

| T | mean CI width | vs T=10 | verdict agreement | sign agreement |
|---|---|---|---|---|
| 10 | 0.3615 | 1.000 | 0.533 | 0.954 |
| 20 | 0.2713 | 0.750 | 0.735 | 0.992 |
| 30 | 0.2307 | 0.638 | 0.846 | 0.996 |
| 40 | 0.2018 | 0.558 | 0.881 | 1.000 |
| 60 | 0.1720 | 0.476 | 1.000 | 1.000 |

## 2. Precision gained by adding REPETITIONS (tasks fixed at 60)

| R_A | R_B | mean CI width | vs R_A=2,R_B=2 |
|---|---|---|---|
| 2 | 2 | 0.2552 | 1.000 |
| 2 | 3 | 0.2346 | 0.919 |
| 2 | 5 | 0.2333 | 0.914 |
| 3 | 2 | 0.2055 | 0.805 |
| 3 | 3 | 0.1958 | 0.767 |
| 3 | 5 | 0.1828 | 0.716 |
| 5 | 2 | 0.1937 | 0.759 |
| 5 | 3 | 0.1847 | 0.724 |
| 5 | 5 | 0.1806 | 0.708 |
| 8 | 2 | 0.1814 | 0.711 |
| 8 | 3 | 0.1756 | 0.688 |
| 8 | 5 | 0.1720 | 0.674 |

## Comparison

- going from 10 to 60 tasks (reps fixed 8/5) narrows intervals by **52.4%**
- going from 2/2 to 8/5 repetitions (tasks fixed 60) narrows them by **32.6%**

On this data the task axis is the stronger lever, but the effect is conditional on already having enough repetitions to estimate $W_A$ at all. No universal optimum is claimed.


---

# Formal definition of the headline numbers

**Appended as a clarification. The numbers above are unchanged.**

These figures must not be quoted without the definition below. They are
**relative reductions in the mean 95% bootstrap confidence-interval width of
`Delta`**, averaged over the 12 P2 primary candidate x property cells. They are
NOT variance reductions, NOT power gains, and NOT reductions in the effect
itself.

## The 52.4% "tasks" figure

$$\text{reduction}_\text{tasks} = 1 - \frac{\bar{W}(T{=}60,\,R_A{=}8,\,R_B{=}5)}{\bar{W}(T{=}10,\,R_A{=}8,\,R_B{=}5)}$$

| term | value |
|---|---|
| numerator — mean CI width at the **full** design, T=60 | **0.172022** |
| denominator — mean CI width at T=10, repetitions held at 8/5 | **0.361527** |
| ratio | 0.4758 |
| **reduction** | **52.4%** |

Compared configurations: `T=10, R_A=8, R_B=5` (reference for this axis) against
`T=60, R_A=8, R_B=5` (the full design). **Repetitions are held fixed**; only the
task count varies.

## The 32.6% "repetitions" figure

$$\text{reduction}_\text{reps} = 1 - \frac{\bar{W}(T{=}60,\,R_A{=}8,\,R_B{=}5)}{\bar{W}(T{=}60,\,R_A{=}2,\,R_B{=}2)}$$

| term | value |
|---|---|
| numerator — mean CI width at the **full** design | **0.172022** |
| denominator — mean CI width at the minimum repetition budget, T held at 60 | **0.255184** |
| ratio | 0.6741 |
| **reduction** | **32.6%** |

Compared configurations: `T=60, R_A=2, R_B=2` (reference for this axis) against
`T=60, R_A=8, R_B=5`. **Tasks are held fixed**; only repetitions vary.

## Why the two are not directly commensurable

The two axes start from different reference points — a 6x range in tasks
(10 -> 60) against a 4x/2.5x range in repetitions (2 -> 8 incumbent, 2 -> 5
candidate). The comparison shows that **over the ranges this study actually
spans**, the task axis delivers the larger width reduction. It does not
establish a general rate of exchange between a task and a repetition, and no
universal optimum is claimed.

## The verdict-agreement figures

"Verdict agreement" is the fraction of deterministic task subsamples whose
three-way verdict at the frozen tolerance 0.05 matches the full-data verdict
for the same cell, averaged over the 12 P2 cells.

| configuration | verdict agreement |
|---|---|
| `T=10, R_A=8, R_B=5` | **0.5333** |
| `T=20, R_A=8, R_B=5` | 0.7354 |
| `T=30, R_A=8, R_B=5` | 0.8458 |
| `T=40, R_A=8, R_B=5` | 0.8812 |
| `T=60, R_A=8, R_B=5` | **1.0000** |

The endpoints of the range quoted elsewhere are **T=10** and **T=60**, with
repetitions fixed at 8/5.

> **Correction.** An earlier draft quoted this range as `0.533 -> 0.917`. The
> upper endpoint is **1.0000**, not 0.917. The 0.917 figure came from a
> run in which the full-task cell drew a different bootstrap seed from the
> reference it was compared against; with that seeding inconsistency fixed, the
> T=60 cell reproduces its own reference exactly and agreement is
> 1.000 by construction. The correct range is
> **0.533 -> 1.000**.
>
> Note that agreement at T=60 is 1.000 *necessarily*, since that cell IS the
> reference. The informative content of this series is the climb across the
> intermediate task counts, not the endpoint.
